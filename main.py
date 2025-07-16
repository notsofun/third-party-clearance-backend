from flow import review_oss_readme

def run_flow(html_path):
    shared = {"html_path" : html_path}

    flow = review_oss_readme()
    flow.run(shared)

    return shared

run_flow(r"C:\Users\z0054unn\AppData\Local\Temp\MicrosoftEdgeDownloads\42247bdd-ff62-4e85-877a-c2dfdfcb4d5f\LicenseInfo-Core Backend-v1.0.0-2025-07-16_05_21_20.html")