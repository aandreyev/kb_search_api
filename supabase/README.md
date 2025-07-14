# Supabase Development Setup

This directory contains the Supabase CLI project configuration and seed data for the Knowledge Base Search API project.

## Overview

The project uses Supabase's branching feature to provide isolated development environments. This allows you to safely test changes, including the new hybrid search functionality, without affecting production data.

## Directory Structure

```
supabase/
├── config.toml          # Supabase CLI configuration
├── seed.sql             # Main seed file (runs all individual seeds)
├── seed/                # Individual seed files
│   ├── 001_sample_documents.sql
│   ├── 002_sample_document_chunks.sql
│   └── 003_sample_activity_logs.sql
├── migrations/          # Database schema migrations (auto-generated)
├── generate_real_embeddings.py  # Script to create real embeddings
└── README.md           # This file
```

## ⚠️ Important: About the Embeddings

The seed files include **dummy embeddings** that have significant limitations:

### What the Current Seed Data Provides:
- ✅ **API functionality testing** - endpoints work without errors
- ✅ **Database operations** - CRUD operations function correctly
- ✅ **Code structure testing** - RPC calls, joins, data flow
- ✅ **Frontend integration** - UI receives and displays results

### What It **Cannot** Provide:
- ❌ **Meaningful vector similarity** - all similarity scores will be unrealistic
- ❌ **Quality search ranking** - results won't reflect semantic relevance
- ❌ **Realistic hybrid search testing** - can't evaluate algorithm effectiveness

## Embedding Options

### Option 1: Use Dummy Embeddings (Quick Start)
**Use when:** You want to test basic functionality, API integration, or code structure.

The current seed files use constant dummy values (`array_fill(0.01, ARRAY[1024])`). This is fine for:
- Verifying your search API returns results
- Testing frontend integration
- Developing the hybrid search code structure
- Testing database operations and migrations

### Option 2: Generate Real Embeddings (Recommended for Quality Testing)
**Use when:** You want to test actual search quality and ranking algorithms.

1. **Start your embedding service:**
   ```bash
   docker-compose up embedding_service
   ```

2. **Generate real embeddings:**
   ```bash
   cd supabase/seed
   python generate_real_embeddings.py
   ```

3. **Replace the dummy embeddings** in `002_sample_document_chunks.sql` with the generated output

4. **Run the updated seed:**
   ```bash
   supabase db seed
   ```

## Seed Data

The seed files provide realistic test data for developing and testing the hybrid search feature:

### Documents (001_sample_documents.sql)
- **6 sample Australian legal documents** covering various practice areas
- Includes taxation guides, employment law, corporate governance, mining safety, GST rulings, and competition law
- Each document has realistic metadata: authors, law areas, document categories, etc.

### Document Chunks (002_sample_document_chunks.sql)
- **18 text chunks** (3 per document) representing actual document content
- Includes embeddings (dummy by default, real via generation script)
- Content covers key legal concepts and terminology for testing keyword search

### Activity Logs (003_sample_activity_logs.sql)
- **Sample user interactions** including searches, document previews, and downloads
- Represents realistic usage patterns for testing analytics and activity tracking
- Includes different user personas (andrew@adlvlaw.com.au, sarah.mitchell@commerciallaw.com.au)

## Using Seed Data with Supabase Branching

### Option 1: Automatic (Recommended)

When you create a new Supabase branch, it can automatically run your seed files:

1. **Set up branching** in your Supabase dashboard (connect to GitHub repository)
2. **Create a new branch** in your code (e.g., `hybrid-search`)
3. **Push to GitHub** - Supabase will automatically create a database branch
4. **Seeds run automatically** when the branch database is created

### Option 2: Manual via CLI

If you need to manually seed your development branch:

```bash
# Make sure you're connected to your development branch
supabase link --project-ref your-dev-branch-ref

# Run all seed files
supabase db seed

# Or run individual seed files
supabase db seed seed/001_sample_documents.sql
```

### Option 3: Manual via Dashboard

1. Open your **development branch** in the Supabase dashboard
2. Go to **SQL Editor**
3. Copy and paste the contents of `seed.sql`
4. Execute the script

## Testing Search Scenarios

### With Dummy Embeddings (Functional Testing)
You can test that your code works, but similarity scores will be meaningless:
- ✅ API endpoints respond
- ✅ Data is retrieved and formatted correctly
- ✅ Frontend displays results
- ❌ Search ranking is unrealistic

### With Real Embeddings (Quality Testing)
Test actual search effectiveness:

**Vector Search Tests:**
- "tax concessions small business" → Should find CGT documents
- "employment restraints executives" → Should find restraint of trade content
- "director responsibilities corporations" → Should find directors' duties content

**Keyword Search Tests (once implemented):**
- "CGT" → Should find exact matches for capital gains tax
- "ATO" → Should find Australian Taxation Office documents
- "section 180" → Should find specific legal references

**Hybrid Search Tests (your goal):**
- "small business CGT" → Should rank documents with both concepts highly
- "restraint trade executive" → Should find employment law content
- "mining safety WA" → Should find Western Australian mining documents

## Data Characteristics

The seed data is designed to test various aspects of hybrid search:

### For Keyword Search
- **Specific legal terms**: CGT, ATO, ACCC, DMIRS
- **Section references**: "section 180", "sections 180-184"
- **Acronyms and abbreviations**: WA, GST, etc.
- **Exact phrases**: "restraint of trade", "essential facilities"

### For Vector Search  
- **Conceptual relationships**: "tax concessions" ↔ "CGT relief"
- **Semantic similarity**: "director responsibilities" ↔ "corporate governance"
- **Topic clustering**: Related legal concepts within practice areas

### For Combined Ranking
- **Documents with both keyword and semantic relevance**
- **Varying levels of specificity** (broad concepts vs. specific terms)
- **Different document types** (guides, rulings, commentary, analysis)

## Development Workflow Recommendation

1. **Start with dummy embeddings** to develop and test your hybrid search code structure
2. **Generate real embeddings** when you're ready to test search quality
3. **Use the real embeddings** to evaluate and tune your ranking algorithm
4. **Test with various queries** to ensure both keyword and semantic search work well together

## Important Notes

⚠️ **Production Safety**: These seed files are designed for development/testing only. Never run them against production data.

📊 **Realistic Data**: The content represents actual Australian legal concepts and terminology, making it suitable for testing search relevance.

🔄 **Reusable**: You can safely re-run the seed files multiple times. The main `seed.sql` includes optional truncation commands for clean resets.

💡 **Embedding Quality**: For meaningful search testing, invest the time to generate real embeddings using the provided script. 