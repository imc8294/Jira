import requests

from requests.auth import HTTPBasicAuth
 
class JiraClient:

    def __init__(self, base_url, email=None, api_token=None, jwt_token=None, verify_ssl=True):

        """

        Initializes the Jira API Client for Jira Cloud API v3.

        """

        self.base_url = base_url.rstrip("/")

        self.verify_ssl = verify_ssl

        self.headers = {

            "Accept": "application/json",

            "Content-Type": "application/json",

            "User-Agent": "StreamlitJiraApp/1.0"

        }
 
        if jwt_token:

            self.headers["Authorization"] = f"JWT {jwt_token}"

            self.auth = None

        else:

            # For Jira Cloud: Username is Email, Password is API Token

            self.auth = HTTPBasicAuth(email, api_token) if email and api_token else None
 
    def _request(self, method, url, **kwargs):

        """Unified internal request handler."""

        kwargs['headers'] = self.headers

        kwargs['verify'] = self.verify_ssl

        if self.auth:

            kwargs['auth'] = self.auth

        resp = requests.request(method, url, **kwargs)

        self._raise(resp)

        return resp
 
    def _raise(self, resp):

        """Error handling for Jira API responses."""

        if not resp.ok:

            try:

                # Capture the specific error message from Jira's JSON response

                err_data = resp.json()

                msg = err_data.get("errorMessages", [resp.text])[0]

            except Exception:

                msg = resp.text

            raise Exception(f"Jira API Error {resp.status_code}: {msg}")
 
    # --- User & Projects ---

    def get_myself(self):

        """Validate login and get user profile."""

        url = f"{self.base_url}/rest/api/3/myself"

        return self._request("GET", url).json()
 
    def get_projects(self):

        """List all accessible projects."""

        url = f"{self.base_url}/rest/api/3/project/search"

        return self._request("GET", url).json().get("values", [])
 
    # --- Issue Management ---

    def search_issues(self, jql, max_results=100, fields=None):

        """Execute JQL Search (Corrected v3 Endpoint)."""

        url = f"{self.base_url}/rest/api/3/search"

        if not fields:

            fields = ["summary", "project", "issuetype", "assignee", "status"]

        payload = {

            "jql": jql,

            "maxResults": int(max_results),

            "fields": fields

        }

        return self._request("POST", url, json=payload).json().get("issues", [])
 
    def get_my_issues(self, jql=None, max_results=100):

        """Fetch issues assigned to the logged-in user."""

        if not jql:

            jql = "assignee = currentUser() ORDER BY updated DESC"

        return self.search_issues(jql=jql, max_results=max_results)
 
    def create_issue(self, project_key, summary, description, issue_type="Task", epic_name=None):

        """Create a Jira issue using ADF (Atlassian Document Format)."""

        url = f"{self.base_url}/rest/api/3/issue"

        payload = {

            "fields": {

                "project": {"key": project_key},

                "summary": summary,

                "description": {

                    "type": "doc", "version": 1,

                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description or ""}]}]

                },

                "issuetype": {"name": issue_type}

            }

        }

        if issue_type == "Epic" and epic_name:

            payload["fields"]["customfield_10011"] = epic_name # Standard Epic Name field

        return self._request("POST", url, json=payload).json()
 
    # --- Worklog Management ---

    def get_worklogs(self, issue_key):

        """Fetch worklogs with pagination support."""

        all_worklogs = []

        start_at = 0

        while True:

            url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"

            params = {"startAt": start_at, "maxResults": 100}

            data = self._request("GET", url, params=params).json()

            worklogs = data.get("worklogs", [])

            all_worklogs.extend(worklogs)

            if start_at + 100 >= data.get("total", 0): break

            start_at += 100

        return all_worklogs
 
    def add_worklog(self, issue_key, time_spent, comment, started):

        """Post a new worklog entry."""

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"

        payload = {"timeSpent": time_spent, "started": started}

        if comment:

            payload["comment"] = {

                "type": "doc", "version": 1,

                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]

            }

        return self._request("POST", url, json=payload).json()
 
    def update_worklog(self, issue_key, worklog_id, hours, comment):

        """Update existing worklog entry."""

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"

        time_seconds = int(float(hours) * 3600)

        payload = {

            "timeSpentSeconds": time_seconds,

            "comment": {

                "type": "doc", "version": 1,

                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]

            }

        }

        return self._request("PUT", url, json=payload).json()
 
    def delete_worklog(self, issue_key, worklog_id):

        """Remove a worklog entry."""

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog/{worklog_id}"

        return self._request("DELETE", url)
 
 


# import requests
# from requests.auth import HTTPBasicAuth

# class JiraClient:
#     def __init__(self, base_url, email=None, api_token=None, jwt_token=None, verify_ssl=True):
#         self.base_url = base_url.rstrip("/")
#         self.verify_ssl = verify_ssl
#         self.headers = {
#             "Accept": "application/json",
#             "Content-Type": "application/json"
#         }

#         # Handle JWT vs Basic Auth
#         if jwt_token:
#             # Forge Bridge mode: Jira expects "JWT <token>"
#             self.headers["Authorization"] = f"JWT {jwt_token}"
#             self.auth = None
#         else:
#             # Standalone mode: email + api_token
#             self.auth = HTTPBasicAuth(email, api_token) if email and api_token else None

#     # -----------------------------
#     # Internal request helper (Crucial for clean code)
#     # -----------------------------
#     def _request(self, method, url, **kwargs):
#         """Unified helper to inject headers and auth automatically."""
#         kwargs['headers'] = self.headers
#         kwargs['verify'] = self.verify_ssl
#         if self.auth:
#             kwargs['auth'] = self.auth
        
#         resp = requests.request(method, url, **kwargs)
#         self._raise(resp)
#         return resp

#     def _raise(self, resp):
#         if not resp.ok:
#             try:
#                 msg = resp.json()
#             except Exception:
#                 msg = resp.text
#             raise Exception(f"Jira API Error {resp.status_code}: {msg}")

#     # -----------------------------
#     # API Methods
#     # -----------------------------
#     def get_myself(self):
#         url = f"{self.base_url}/rest/api/3/myself"
#         return self._request("GET", url).json()

#     def search_issues(self, jql, max_results=100, fields=None):
#         url = f"{self.base_url}/rest/api/3/search/jql"
#         if not fields:
#             fields = ["summary", "project", "issuetype", "assignee", "status"]
        
#         payload = {
#             "jql": jql,
#             "maxResults": int(max_results),
#             "fields": fields
#         }
#         return self._request("POST", url, json=payload).json().get("issues", [])

#     def get_my_issues(self, jql=None, max_results=100):
#         if not jql:
#             jql = "assignee = currentUser() ORDER BY updated DESC"
#         return self.search_issues(jql=jql, max_results=max_results)

#     def get_projects(self):
#         url = f"{self.base_url}/rest/api/3/project/search"
#         return self._request("GET", url).json().get("values", [])

#     def create_issue(self, project_key, summary, description, issue_type="Task"):
#         url = f"{self.base_url}/rest/api/3/issue"
#         payload = {
#             "fields": {
#                 "project": {"key": project_key},
#                 "summary": summary,
#                 "description": {
#                     "type": "doc", "version": 1,
#                     "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]
#                 },
#                 "issuetype": {"name": issue_type}
#             }
#         }
#         return self._request("POST", url, json=payload).json()

#     def add_worklog(self, issue_key, time_spent, comment, started):
#         url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
#         payload = {"timeSpent": time_spent, "started": started}
#         if comment:
#             payload["comment"] = {
#                 "type": "doc", "version": 1,
#                 "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]
#             }
#         return self._request("POST", url, json=payload).json()

#     def get_worklogs(self, issue_key):
#         all_worklogs = []
#         start_at = 0
#         while True:
#             url = f"{self.base_url}/rest/api/3/issue/{issue_key}/worklog"
#             params = {"startAt": start_at, "maxResults": 100}
#             data = self._request("GET", url, params=params).json()
#             worklogs = data.get("worklogs", [])
#             all_worklogs.extend(worklogs)
#             if start_at + 100 >= data.get("total", 0): break
#             start_at += 100
#         return all_worklogs
