from flow import review_oss_readme

def run_flow(html_path):
    shared = {"html_path" : html_path}

    flow = review_oss_readme()
    flow.run(shared)

    return shared

run_flow(r"C:\Users\z0054unn\Downloads\LicenseInfo-Core Backend-v1.0.0-2025-07-17_03_23_03.html")