import os
import json
import re
from neo4j import GraphDatabase
from pydriller import Repository

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password")

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
        py_files = []
        for root, dirs, files in os.walk(repo_path):
            if '.git' in root:
                continue
            for file in files:
                if file.endswith('.py'):
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    py_files.append(rel_path)
        
        with self.driver.session() as session:
            for file_path in py_files:
                session.run("MERGE (f:File {name: $name})", name=file_path)
                
                abs_path = os.path.join(repo_path, file_path)
                with open(abs_path, 'r') as f:
                    lines = f.readlines()
                
                current_func = None
                for line in lines:
                    line = line.strip()
                    if line.startswith("def "):
                        func_name = line.split("def ")[1].split("(")[0].strip()
                        current_func = func_name
                        session.run("""
                            MERGE (f:Function {name: $func_name})
                            WITH f
                            MATCH (file:File {name: $file_name})
                            MERGE (file)-[:DEFINES]->(f)
                        """, func_name=func_name, file_name=file_path)
                        
                    # Semantic Dependency Tracing for Monolith Demo
                    if current_func:
                        if "is_legacy_billing_enabled" in line and not line.startswith("def "):
                            session.run("""
                                MERGE (caller:Function {name: $caller})
                                MERGE (callee:Function {name: 'is_legacy_billing_enabled'})
                                MERGE (caller)-[:IMPORTS]->(callee)
                            """, caller=current_func)
                        if "process_payment" in line and not line.startswith("def "):
                            session.run("""
                                MERGE (caller:Function {name: $caller})
                                MERGE (callee:Function {name: 'process_payment'})
                                MERGE (caller)-[:IMPORTS]->(callee)
                            """, caller=current_func)
                        if "calculate_shipping" in line and not line.startswith("def "):
                            session.run("""
                                MERGE (caller:Function {name: $caller})
                                MERGE (callee:Function {name: 'calculate_shipping'})
                                MERGE (caller)-[:IMPORTS]->(callee)
                            """, caller=current_func)

    def ingest_git(self, repo_path):
        print("Ingesting Git History...")
        with self.driver.session() as session:
            for commit in Repository(repo_path).traverse_commits():
                author_name = commit.author.name
                commit_hash = commit.hash
                msg = commit.msg
                
                session.run("""
                    MERGE (c:Commit {hash: $commit_hash, author: $author_name, msg: $msg})
                """, author_name=author_name, commit_hash=commit_hash, msg=msg)
                
                for modified_file in commit.modified_files:
                    file_name = modified_file.new_path or modified_file.old_path
                    if file_name:
                        session.run("""
                            MATCH (c:Commit {hash: $commit_hash})
                            MATCH (f:File {name: $file_name})
                            MERGE (c)-[:MODIFIED]->(f)
                        """, commit_hash=commit_hash, file_name=file_name)

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
                    MATCH (f:File {name: $file_name})
                    MERGE (t:JiraTicket {ticket_id: $ticket_id})
                    MERGE (e:Epic {name: $epic_name})
                    MERGE (f)-[:PART_OF]->(t)
                    MERGE (t)-[:BELONGS_TO]->(e)
                """, file_name=issue['file'], ticket_id=issue['ticket_id'], epic_name=issue['epic'])

if __name__ == "__main__":
    repo = "."
    engine = IngestionEngine(URI, AUTH)
    engine.clear_database()
    engine.ingest_code(repo)
    engine.ingest_git(repo)
    engine.ingest_jira(repo)
    engine.close()
    print("Ingestion complete!")
