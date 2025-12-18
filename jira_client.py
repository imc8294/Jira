import requests
from requests.auth import HTTPBasicAuth

class JiraClient:
    def __init__(self, base_url, email, api_token, verify_ssl=True):
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        self.auth = HTTPBasicAuth(email, api_token)

    # -----------------------------
    # Internal error handler
    # -----------------------------
    def _raise(self, resp):
        if not resp.ok:
            try:
                msg = resp.json()
            except Exception:
                msg = resp.text
            raise Exception(
                f"Jira API Error {resp.status_code}: {msg}"
            )

    # -----------------------------
    # Auth check
    # -----------------------------
    def get_myself(self):
        url = f"{self.base_url}/rest/api/3/myself"
        resp = requests.get(
            url,
            headers=self.headers,
            auth=self.auth,
            verify=self.verify_ssl
        )
        self._raise(resp)
        return resp.json()

    # -----------------------------
    # Generic issue search
    # -----------------------------
    def search_issues(self, jql, max_results=100, fields=None):
        url = f"{self.base_url}/rest/api/3/search/jql"

        if not fields:
            fields = ["summary", "project", "issuetype"]

        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields
        }

        resp = requests.post(
            url,
            headers=self.headers,
            auth=self.auth,
            json=payload,
            verify=self.verify_ssl
        )
        self._raise(resp)
        return resp.json().get("issues", [])

    # -----------------------------
    # My assigned issues
    # -----------------------------
    def get_my_issues(self, jql=None, max_results=100, fields=None):
        if not jql:
            jql = "assignee = currentUser() ORDER BY updated DESC"

        return self.search_issues(
            jql=jql,
            max_results=max_results,
            fields=fields
        )

    # -----------------------------
    # Get all projects
    # -----------------------------
    def get_projects(self):
        url = f"{self.base_url}/rest/api/3/project/search"
        resp = requests.get(
            url,
            headers=self.headers,
            auth=self.auth,
            verify=self.verify_ssl
        )
        self._raise(resp)
        return resp.json().get("values", [])


    # -----------------------------
    # Create issue
    # -----------------------------

    def create_issue(self, project_key, summary, description, issue_type, epic_name=None):
        url = f"{self.base_url}/rest/api/3/issue"

        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ]
                    }
                ]
            }
        }

        # Epic requires Epic Name
        if issue_type == "Epic":
            fields["customfield_10011"] = epic_name  # Epic Name field

        payload = {"fields": fields}

        resp = requests.post(
            url,
            headers=self.headers,
            auth=self.auth,
            json=payload,
            verify=self.verify_ssl
        )
        self._raise(resp)
        return resp.json()

    # -----------------------------
    # Add worklog
    # -----------------------------
    def add_worklog(self, issue_key, time_spent, comment, started):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"

        payload = {
            "timeSpent": time_spent,
            "started": started
        }

        if comment:
            payload["comment"] = {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": comment}
                        ]
                    }
                ]
            }

        resp = requests.post(
            url,
            headers=self.headers,
            auth=self.auth,
            json=payload,
            verify=self.verify_ssl
        )
        self._raise(resp)
        return resp.json()

    # -----------------------------
    # Get worklogs (paginated)
    # -----------------------------
    def get_worklogs(self, issue_key):
        all_worklogs = []
        start_at = 0
        max_results = 100

        while True:
            url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
            params = {
                "startAt": start_at,
                "maxResults": max_results
            }

            resp = requests.get(
                url,
                headers=self.headers,
                auth=self.auth,
                params=params,
                verify=self.verify_ssl
            )
            self._raise(resp)

            data = resp.json()
            worklogs = data.get("worklogs", [])
            all_worklogs.extend(worklogs)

            if start_at + max_results >= data.get("total", 0):
                break

            start_at += max_results

        return all_worklogs
    



    # -----------------------------
    # Update worklog
    # -----------------------------
    def update_worklog(self, issue_key, worklog_id, hours, comment):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"

        payload = {
            "timeSpentSeconds": int(hours * 3600),
            "comment": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": comment}]
                }]
            }
        }

        resp = requests.put(url, headers=self.headers, auth=self.auth, json=payload)
        self._raise(resp)


    def delete_worklog(self, issue_key, worklog_id):
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"
        resp = requests.delete(url, headers=self.headers, auth=self.auth)
        self._raise(resp)

