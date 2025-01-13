import requests
import os
import base64

# Azure DevOps Organization, Personal Access Token (PAT), and Header details
org_url = 'https://dev.azure.com/{org_name}/'  # Replace {org_name} with your Azure DevOps organization name
pat_token = '{PAT}'  # Replace with your PAT with access to all repo
headers = {
    "Authorization": f"Basic {base64.b64encode(f':{pat_token}'.encode()).decode()}",
    "Content-Type": "application/json"
}

# Step 1: Get all projects
def get_projects():
    url = f"{org_url}_apis/projects?api-version=7.0"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["value"]
    else:
        print("Failed to get projects")
        print(response.status_code, response.json())
        return []

# Step 2: Get repositories for a specific project
def get_repos_for_project(project_id):
    url = f"{org_url}{project_id}/_apis/git/repositories?api-version=7.0"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()["value"]
    else:
        print(f"Failed to get repositories for project {project_id}")
        print(response.status_code, response.json())
        return []

# Step 3: Add/Update Function
def update_repo_with_yaml(project_id, project_name, repo_id, repo_name, branch_name="main"):
    # YAML content for ADD
    yaml_content_add = """
# Starter pipeline
# https://aka.ms/yaml

trigger:
- main

pool:
  vmImage: ubuntu-latest

steps:
- task: set-key-vault@1.1.0
  displayName: 'Set key vault name'
  continueOnError: true
- task: AzureKeyVault@2
  displayName: 'Veracode azure key vault'
  inputs:
    azureSubscription: 'Veracode Service Connection-$(System.TeamProject)'
    KeyVaultName: '$(keyVaultName)'
    SecretsFilter: 'UserPat, VeracodeApiId, VeracodeApiKey, ScaApiToken, SrcclrApiUrl'
    RunAsPreJob: false
  continueOnError: true
    """.strip()

    # YAML content for EDIT
    yaml_content_edit = """
- task: set-key-vault@1.1.0
  displayName: 'Set key vault name'
  continueOnError: true
- task: AzureKeyVault@2
  displayName: 'Veracode azure key vault'
  inputs:
    azureSubscription: 'Veracode Service Connection-$(System.TeamProject)'
    KeyVaultName: '$(keyVaultName)'
    SecretsFilter: 'UserPat, VeracodeApiId, VeracodeApiKey, ScaApiToken, SrcclrApiUrl'
    RunAsPreJob: false
  continueOnError: true
    """.strip()

    # Step 4: Get the latest commit ID for the branch
    branch_url = f"{org_url}{project_id}/_apis/git/repositories/{repo_id}/refs?filter=heads/{branch_name}&api-version=7.0"
    branch_response = requests.get(branch_url, headers=headers)
    if branch_response.status_code != 200:
        print(f"Failed to get branch details for branch '{branch_name}' in repository '{repo_name}' under project '{project_name}': {branch_response.text}")
        return

    branch_data = branch_response.json()
    if not branch_data["value"]:
        print(f"\nBranch '{branch_name}' not found in repository '{repo_name}' under project '{project_name}'. Checking for Master Branch")
        branch_name = "master"
        branch_url = f"{org_url}{project_id}/_apis/git/repositories/{repo_id}/refs?filter=heads/{branch_name}&api-version=7.0"
        branch_response = requests.get(branch_url, headers=headers)
        if branch_response.status_code != 200:
            print(f"Failed to get branch details for branch '{branch_name}' in repository '{repo_name}' under project '{project_name}': {branch_response.text}")
            return
        
        branch_data = branch_response.json()
        if not branch_data["value"]:
            print(f"Branch '{branch_name}' not found in repository '{repo_name}' under project '{project_name}'. Skipping this repository.")
            return

    latest_commit_id = branch_data["value"][0]["objectId"]

    # Step 5: Create a push request to add the file
    push_url = f"{org_url}{project_id}/_apis/git/repositories/{repo_id}/pushes?api-version=7.0"
    push_data_add = {
        "refUpdates": [
            {
                "name": f"refs/heads/{branch_name}",
                "oldObjectId": latest_commit_id
            }
        ],
        "commits": [
            {
                "comment": "Add azure-pipelines.yml",
                "changes": [
                    {
                        "changeType": "add",
                        "item": {
                            "path": "/azure-pipelines.yml"
                        },
                        "newContent": {
                            "content": yaml_content_add,
                            "contentType": "rawtext"
                        }
                    }
                ]
            }
        ]
    }

    push_response = requests.post(push_url, headers=headers, json=push_data_add)
    if push_response.status_code == 201:
        print(f"\nSuccessfully added 'azure-pipelines.yml' to repository '{repo_name}' under project '{project_name}'.")
        return
    elif push_response.status_code == 400 and "already exists" in push_response.json().get("message", "").lower():
        print(f"\nFile already exists in repository '{repo_name}' under project '{project_name}'. Attempting to update it instead.")
    else:
        print(f"\nFailed to add 'azure-pipelines.yml' to repository '{repo_name}' under project '{project_name}'.")
        print(push_response.status_code, push_response.json())
        return

    # Step 3: Retrieve existing file content for EDIT
    file_url = f"{org_url}{project_id}/_apis/git/repositories/{repo_id}/items?path=/azure-pipelines.yml&versionDescriptor.version={branch_name}&api-version=7.0"
    file_response = requests.get(file_url, headers=headers)
    if file_response.status_code == 200:
        existing_yaml = file_response.text
        if yaml_content_edit in existing_yaml:
            print(f"\nYAML content for EDIT already exists in 'azure-pipelines.yml' in repository '{repo_name}' under project '{project_name}'. Skipping edit.")
            return
        updated_yaml = existing_yaml.strip() + "\n\n" + yaml_content_edit
    else:
        print(f"\nFailed to retrieve the existing file content for repository '{repo_name}' under project '{project_name}'.")
        print(file_response.status_code, file_response.json())
        return

    # Step 6: Create a push request to edit the file
    push_data_edit = {
        "refUpdates": [
            {
                "name": f"refs/heads/{branch_name}",
                "oldObjectId": latest_commit_id
            }
        ],
        "commits": [
            {
                "comment": "Update azure-pipelines.yml",
                "changes": [
                    {
                        "changeType": "edit",
                        "item": {
                            "path": "/azure-pipelines.yml"
                        },
                        "newContent": {
                            "content": updated_yaml,
                            "contentType": "rawtext"
                        }
                    }
                ]
            }
        ]
    }

    push_response = requests.post(push_url, headers=headers, json=push_data_edit)
    if push_response.status_code == 201:
        print(f"\nSuccessfully updated 'azure-pipelines.yml' in repository '{repo_name}' under project '{project_name}'.")
    else:
        print(f"\nFailed to update 'azure-pipelines.yml' in repository '{repo_name}' under project '{project_name}'.")
        print(push_response.status_code, push_response.json())

# Main function
def main():
    projects = get_projects()

    for project in projects:
        project_id = project["id"]
        project_name = project["name"]

        if project_name.lower() == "veracode":
            continue  # Skip the "veracode" project

        repos = get_repos_for_project(project_id)

        for repo in repos:
            repo_id = repo["id"]
            repo_name = repo["name"]
            
            update_repo_with_yaml(project_id, project_name, repo_id, repo_name)

if __name__ == "__main__":
    main()
