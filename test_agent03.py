from shared import db
from agents.contact_discovery_agent import process_company

print("getting companies...")
companies = db.get_company_targets_for_contact_discovery(2)
print(f"got {len(companies)} companies")

for company in companies:
    print(f"\nprocessing {company['company_name']}...")
    result = process_company(2, company)
    print(f"result: {result}")