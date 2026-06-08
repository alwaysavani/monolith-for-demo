import sys
import os
import json
import subprocess
from neo4j import GraphDatabase
from google import genai

URI = "neo4j://localhost:7687"
AUTH = ("neo4j", "password")

def get_blast_radius(changed_files):
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    query = """
    UNWIND $files AS filename
    MATCH (changed_file:File {name: filename})-[:DEFINES]->(func:Function)
    MATCH path = (func)<-[:CALLS|IMPORTS*1..5]-(downstream_func:Function)<-[:DEFINES]-(impacted_file:File)
    WHERE impacted_file.name <> filename
    OPTIONAL MATCH (impacted_file)<-[:MODIFIED]-(c:Commit)
    OPTIONAL MATCH (impacted_file)-[:PART_OF]->(t:JiraTicket)-[:BELONGS_TO]->(e:Epic)
    RETURN distinct impacted_file.name AS file, c.author AS author, t.ticket_id AS ticket, e.name AS epic
    """
    
    records, _, _ = driver.execute_query(query, files=changed_files, database_="neo4j")
    
    results = []
    reviewers = set()
    for record in records:
        results.append(dict(record))
        if record.get("author"):
            reviewers.add(record["author"])
            
    return results, list(reviewers)

def generate_and_post_comment(changed_files, blast_radius, reviewers):
    if not blast_radius:
        print("No blast radius detected. Exiting cleanly.")
        return
        
    client = genai.Client()
    prompt = f"""
    You are the 'Graph-RAG PR Blocker', an automated CI/CD pipeline agent.
    A developer has opened a PR modifying these files: {changed_files}.
    
    Based on our Neo4j graph traversal, this silently breaks the following downstream dependencies:
    {json.dumps(blast_radius, indent=2)}
    
    Draft a GitHub PR comment (in Markdown).
    - Start with a massive warning emoji and a bold header.
    - Explicitly list the downstream modules, Jira tickets, and Epics broken by this change.
    - State that the Semantic Code Owners ({', '.join(['@' + r.replace(' ', '') for r in reviewers])}) have been automatically assigned to review.
    - Keep it under 200 words. Do not use a top-level code block.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    comment = response.text
    
    with open("comment.md", "w") as f:
        f.write(comment)
        
    pr_url = f"https://github.com/{os.environ['REPO_NAME']}/pull/{os.environ['PR_NUMBER']}"
    
    try:
        subprocess.run(["gh", "pr", "comment", pr_url, "-F", "comment.md"], env=os.environ, check=True)
        print("Successfully posted PR comment!")
    except subprocess.CalledProcessError as e:
        print(f"Failed to post comment. Ensure GITHUB_TOKEN has write access. {e}")
        print(f"Comment generated:\n{comment}")

if __name__ == "__main__":
    changed_files = sys.argv[1:]
    if not changed_files:
        print("No Python files changed. Exiting.")
        sys.exit(0)
        
    print(f"Analyzing blast radius for: {changed_files}")
    blast_radius, reviewers = get_blast_radius(changed_files)
    
    print(f"Found {len(blast_radius)} impacted downstream items.")
    generate_and_post_comment(changed_files, blast_radius, reviewers)
    
    if blast_radius:
        print("Blast radius detected. Failing the CI check to block the PR.")
        sys.exit(1)
