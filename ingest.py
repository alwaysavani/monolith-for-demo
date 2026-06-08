import os
import json
import re
from neo4j import GraphDatabase
# tree_sitter not strictly needed if we do simple string matching for the demo, 
# but imported for authenticity in the "real" architecture.
from pydriller import Repository

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password")
MOCK_REPO_DIR = "."  # Analyze the root of the monolith repo directly

class IngestionEngine:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def clear_database(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Cleared database.")

    def ingest_code(self, repo_path):
        print("Ingesting Code AST...")
        files_to_parse = ['db.py', 'auth.py', 'cart.py', 'checkout_api.py']
        
        with self.driver.session() as session:
            for file_name in files_to_parse:
                file_path = os.path.join(repo_path, file_name)
                if not os.path.exists(file_path):
                    continue
                
                # Create File Node
                session.run("MERGE (f:File {name: $name})", name=file_name)
                
                # Simplified parsing for the 5 min demo to ensure perfect deterministic graph
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                current_func = None
                for line in lines:
                    if line.startswith("def "):
                        func_name = line.split("def ")[1].split("(")[0].strip()
                        current_func = func_name
                        session.run("""
                            MERGE (f:Function {name: $func_name})
                            WITH f
                            MATCH (file:File {name: $file_name})
                            MERGE (f)-[:DEFINED_IN]->(file)
                        """, func_name=func_name, file_name=file_name)
                    elif current_func and "(" in line and ")" in line:
                        # naive call detection
                        words = line.replace("(", " ").replace(")", " ").replace(".", " ").split()
                        for word in words:
                            if word in ['check_legacy_flag', 'get_user_record', 'verify_user', 'apply_discount', 'process_order']:
                                if word != current_func:
                                    session.run("""
                                        MERGE (caller:Function {name: $caller})
                                        MERGE (callee:Function {name: $callee})
                                        MERGE (caller)-[:CALLS]->(callee)
                                    """, caller=current_func, callee=word)

    def ingest_git(self, repo_path):
        print("Ingesting Git History...")
        with self.driver.session() as session:
            for commit in Repository(repo_path).traverse_commits():
                author_name = commit.author.name
                commit_hash = commit.hash
                msg = commit.msg
                
                session.run("""
                    MERGE (d:Developer {name: $author_name})
                    MERGE (c:Commit {hash: $commit_hash, msg: $msg})
                    MERGE (d)-[:AUTHORED]->(c)
                """, author_name=author_name, commit_hash=commit_hash, msg=msg)
                
                for modified_file in commit.modified_files:
                    file_name = modified_file.filename
                    session.run("""
                        MATCH (c:Commit {hash: $commit_hash})
                        MATCH (f:File {name: $file_name})
                        MERGE (c)-[:MODIFIED]->(f)
                    """, commit_hash=commit_hash, file_name=file_name)
                    
                # Link Commit to Jira if mentioned in msg (e.g. [PAY-992])
                match = re.search(r'\[([A-Z]+-\d+)\]', msg)
                if match:
                    ticket_id = match.group(1)
                    session.run("""
                        MATCH (c:Commit {hash: $commit_hash})
                        MERGE (t:JiraTicket {id: $ticket_id})
                        MERGE (c)-[:IMPLEMENTS]->(t)
                    """, commit_hash=commit_hash, ticket_id=ticket_id)

    def ingest_jira(self, repo_path):
        print("Ingesting Business Data...")
        issues_path = os.path.join(repo_path, 'issues.json')
        if not os.path.exists(issues_path):
            return
            
        with open(issues_path, 'r') as f:
            issues = json.load(f)
            
        with self.driver.session() as session:
            for issue in issues:
                session.run("""
                    MERGE (t:JiraTicket {id: $ticket_id})
                    SET t.description = $desc, t.status = $status
                    MERGE (e:Epic {name: $epic_name})
                    MERGE (t)-[:PART_OF]->(e)
                """, ticket_id=issue['ticket_id'], desc=issue['description'], status=issue['status'], epic_name=issue['epic'])

if __name__ == "__main__":
    repo = "./mock_repo"
    engine = IngestionEngine(URI, AUTH)
    engine.clear_database()
    engine.ingest_code(repo)
    engine.ingest_git(repo)
    engine.ingest_jira(repo)
    engine.close()
    print("Ingestion complete!")
