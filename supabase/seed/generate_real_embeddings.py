#!/usr/bin/env python3
"""
Generate real embeddings for seed data using the embedding service.
This script takes the text content from our seed files and generates 
actual embeddings that can be used for realistic testing.

Usage:
1. Make sure your embedding service is running
2. Set EMBEDDING_SERVICE_URL environment variable
3. Run: python generate_real_embeddings.py
4. Copy the output to replace dummy embeddings in 002_sample_document_chunks.sql
"""

import os
import requests
import json
from typing import List

# Configuration
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")

# The actual content from our seed data
CHUNK_CONTENTS = [
    # Document 1 - Small Business CGT Concessions
    "Small business capital gains tax (CGT) concessions provide significant tax relief for eligible small businesses when disposing of active assets or business interests. The main concessions include the 15-year exemption, 50% active asset reduction, retirement exemption, and rollover relief. These concessions can substantially reduce or eliminate CGT liability for qualifying small business owners.",
    
    "To access small business CGT concessions, businesses must satisfy the basic conditions including the $6 million net asset value test, active asset test (80% for companies and trusts, 90% for individuals), and carrying on a business test. The aggregated turnover threshold is $2 million for most concessions, though some have higher thresholds.",
    
    "The small business 15-year exemption allows a complete exemption from CGT if you continuously owned the CGT asset for at least 15 years and you are aged 55 or over and retiring, or permanently incapacitated. This exemption applies to assets continuously owned since before 1 January 1999 for individuals, or since incorporation for companies.",
    
    # Document 2 - Restraint of Trade
    "Restraint of trade clauses in executive employment contracts must be reasonable in scope, duration, and geographical limitation to be enforceable under Australian law. Courts will not enforce restraints that go beyond what is necessary to protect the employer's legitimate business interests, such as confidential information, customer relationships, or trade secrets.",
    
    "The enforceability of restraint of trade provisions depends on several factors: the seniority of the employee, access to confidential information, customer contact, competition with the former employer, and whether the restraint is supported by adequate consideration. Executive positions typically justify broader restraints due to their access to strategic information.",
    
    "Geographical limitations in restraint clauses must correspond to the employer's actual market presence. A worldwide restraint may be justified for multinational executives, while local restraints are more appropriate for regional roles. Time limitations typically range from 6 months to 2 years, with longer periods requiring stronger justification.",
    
    # Document 3 - Directors Duties
    "Directors of Australian corporations owe statutory duties under sections 180-184 of the Corporations Act 2001. These include the duty to exercise care and diligence (s180), act in good faith in the best interests of the corporation (s181), not to improperly use position (s182), and not to improperly use information (s183).",
    
    "The business judgment rule in section 180(2) provides protection for directors who make business decisions in good faith, for a proper purpose, without material personal interest, inform themselves appropriately, and rationally believe the decision is in the best interests of the corporation. This rule recognizes that business involves risk and uncertainty.",
    
    "Fiduciary duties require directors to act in the best interests of the corporation as a whole, avoid conflicts of interest, and not to profit from their position without proper authorization. These duties exist alongside statutory obligations and can result in both civil and criminal liability for breaches.",
    
    # Document 4 - Mining Safety WA
    "Western Australian mining operations must comply with the Work Health and Safety Act 2020 and Mining Regulations. Key requirements include safety management systems, risk assessments, worker consultation, incident reporting, and regular safety audits. The Department of Mines, Industry Regulation and Safety (DMIRS) enforces these requirements.",
    
    "Mining safety compliance requires comprehensive risk management including hazard identification, risk assessment, and implementation of control measures. Priority hazards in WA mining include falls from height, vehicle interactions, explosions, inrush/instability, and exposure to hazardous substances. Regular safety training and competency assessments are mandatory.",
    
    "Reporting obligations for mining operations include immediate notification of serious incidents, regular safety performance reporting, and annual compliance certificates. Penalties for non-compliance can include substantial fines, prosecution of company officers, and suspension of mining operations. DMIRS conducts regular inspections and investigations.",
    
    # Document 5 - GST Input Tax Credits
    "Professional service providers can claim GST input tax credits for business-related purchases, provided they are registered for GST and the acquisitions are for a creditable purpose. Input tax credits are available for office expenses, professional development, business equipment, and other costs directly related to making taxable supplies.",
    
    "Mixed-use assets require apportionment between business and private use for GST input tax credit purposes. Professional service providers must maintain detailed records to substantiate the business portion of expenses. Common mixed-use items include vehicles, mobile phones, home office expenses, and professional subscriptions.",
    
    "The creditable purpose test requires that acquisitions be made for the purpose of making taxable supplies. Input tax credits are not available for private expenses, entertainment (subject to limited exceptions), or acquisitions related to input taxed supplies. Professional service providers must carefully categorize expenses to ensure compliance.",
    
    # Document 6 - Essential Facilities Doctrine
    "The essential facilities doctrine under Australian competition law provides that a business with control over an essential facility cannot refuse access to competitors without legitimate business justification. This doctrine applies where the facility is essential for competition, controlled by a potential competitor, and practically impossible to duplicate.",
    
    "Essential facilities doctrine cases in Australia have involved telecommunications networks, port facilities, payment systems, and exclusive dealing arrangements. The High Court in Melway Publishing v Robert Hicks Pty Ltd established that mere ownership of a facility does not create an obligation to provide access to competitors.",
    
    "ACCC enforcement of essential facilities principles considers market definition, barriers to entry, competitive effects, and potential efficiency justifications. The doctrine balances the property rights of facility owners against the competitive process. Recent cases have focused on digital platforms and data access issues."
]

def get_embedding(text: str) -> List[float]:
    """Get embedding from the embedding service."""
    try:
        response = requests.post(
            f"{EMBEDDING_SERVICE_URL.rstrip('/')}/embed",
            json={"text": text},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        return data.get('embedding', [])
    except Exception as e:
        print(f"Error getting embedding for text: {text[:50]}...")
        print(f"Error: {e}")
        return []

def format_embedding_for_sql(embedding: List[float]) -> str:
    """Format embedding as SQL array."""
    if not embedding:
        return "array_fill(0.0, ARRAY[1024])::vector  -- ERROR: Could not generate embedding"
    
    # Format as PostgreSQL array
    formatted_values = [f"{val:.6f}" for val in embedding]
    return f"ARRAY[{', '.join(formatted_values)}]::vector"

def main():
    print("🚀 Generating real embeddings for seed data...")
    print(f"📡 Using embedding service at: {EMBEDDING_SERVICE_URL}")
    print(f"📝 Processing {len(CHUNK_CONTENTS)} text chunks...")
    print()
    
    # Test connection first
    try:
        test_response = requests.get(f"{EMBEDDING_SERVICE_URL.rstrip('/')}/health", timeout=10)
        if test_response.status_code != 200:
            print("❌ Embedding service not responding. Make sure it's running!")
            return
    except:
        print("❌ Cannot connect to embedding service. Make sure it's running!")
        print("   Start it with: docker-compose up embedding_service")
        return
    
    print("✅ Embedding service is reachable")
    print()
    
    # Generate embeddings
    embeddings = []
    for i, content in enumerate(CHUNK_CONTENTS):
        print(f"Generating embedding {i+1}/{len(CHUNK_CONTENTS)}... ", end="", flush=True)
        embedding = get_embedding(content)
        if embedding:
            print("✅")
            embeddings.append(embedding)
        else:
            print("❌")
            embeddings.append([])
    
    print()
    print("🎯 Generated embeddings! Here's your updated SQL:")
    print("="*80)
    print()
    
    # Output the SQL INSERT statements with real embeddings
    document_id = 1
    chunk_index = 0
    
    for i, (content, embedding) in enumerate(zip(CHUNK_CONTENTS, embeddings)):
        # Move to next document every 3 chunks
        if i > 0 and i % 3 == 0:
            document_id += 1
            chunk_index = 0
        
        sql_embedding = format_embedding_for_sql(embedding)
        
        print(f"-- Chunk {i+1}: Document {document_id}, Chunk {chunk_index}")
        print("(")
        print(f"    {document_id},")
        print(f"    {chunk_index},")
        print(f"    '{content}',")
        print(f"    {sql_embedding}")
        print(")", end="")
        
        if i < len(CHUNK_CONTENTS) - 1:
            print(",")
        else:
            print(";")
        print()
        
        chunk_index += 1
    
    print("="*80)
    print("✅ Copy the above SQL and replace the INSERT VALUES section in:")
    print("   supabase/seed/002_sample_document_chunks.sql")
    print()
    print("💡 Pro tip: Now your seed data will have realistic vector similarity!")

if __name__ == "__main__":
    main() 