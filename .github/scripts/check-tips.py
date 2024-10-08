import re
import os
import json
from github import Github
from difflib import SequenceMatcher

def extract_tips(content):
    pattern = r'- (.*)'
    return [match.strip() for match in re.findall(pattern, content)]

def check_duplicates(new_tips, existing_tips):

    # 80% threshold for similarity
    return [
        (new_tip, existing_tip, similarity)
        for new_tip in new_tips
        for existing_tip in existing_tips
        if (similarity := SequenceMatcher(None, new_tip.lower(), existing_tip.lower()).ratio()) > 0.8
    ]


def extract_changes(patch_content):
    added, removed = [], []
    lines = patch_content.splitlines()
    
    for line in lines:
        if line.startswith('+') and not line.startswith('+++'):
            added.append(line[1:].strip())  # Extract added content without '+'
        elif line.startswith('-') and not line.startswith('---'):
            removed.append(line[1:].strip())  # Extract removed content without '-'
    
    return "\n".join(added), "\n".join(removed)

def main():
    # Load PR event data
    with open(os.environ['GITHUB_EVENT_PATH']) as f:
        event = json.load(f)
    
    pr_number = event['pull_request']['number']
    repo_name = event['repository']['full_name']
    
    # Authenticate with GitHub and fetch PR details
    g = Github(os.environ['GITHUB_TOKEN'])
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    # Look for changes in 'tips.md'
    tips_file = next((file for file in pr.get_files() if file.filename == 'tips.md'), None)
    if not tips_file:
        pr.create_issue_comment("No changes to tips.md found in this PR.")
        return
    
    # Extract added and removed content from the patch
    added_content, removed_content = extract_changes(tips_file.patch)
    
    # Extract new and removed tips
    new_tips = extract_tips(added_content)
    removed_tips = extract_tips(removed_content)
    print("new tips",new_tips,"removed tips",removed_tips)

    # Fetch the tips.md file from the main branch
 
    main_branch_file = repo.get_contents('tips.md', ref='main')
    existing_tips_content = main_branch_file.decoded_content.decode('utf-8')
    existing_tips = extract_tips(existing_tips_content)

    # Prepare a list of all existing tips, excluding removed ones
    all_existing_tips = set(existing_tips).difference(removed_tips)
    print("all existing tips",all_existing_tips,'existing tips',existing_tips)
    # Check for duplicate tips
    duplicates = check_duplicates(new_tips, all_existing_tips)
    
    # Construct result comment
    if duplicates:
        comment = "### Potential Duplicate Tips\n"
        comment += "\n".join(
            f"- New tip: \"{new_tip}\"\n  Similar to: \"{existing_tip}\"\n  Similarity: {similarity:.2%}"
            for new_tip, existing_tip, similarity in duplicates
        )
    else:
        comment = "No duplicates found. All new tips are unique."
    
    pr.create_issue_comment(comment)

if __name__ == "__main__":
    main()
