"""
cleanup_orphaned_collections.py
Finds Qdrant collections with no matching row in Supabase's chatbots
table and deletes them. Safe by default — dry-run unless --confirm is passed.
"""

import sys
from services.database import get_supabase
from services.qdrant_service import _client, delete_collection

def find_orphans():
    # 1. Get every collection name currently in Qdrant
    qdrant_collections = {c.name for c in _client.get_collections().collections}

    # 2. Get every qdrant_collection value Supabase still references
    supabase = get_supabase()
    result = supabase.table("chatbots").select("qdrant_collection").execute()
    active_collections = {
        row["qdrant_collection"] for row in result.data if row.get("qdrant_collection")
    }

    # 3. Orphans = in Qdrant but not referenced by any chatbot row
    orphans = qdrant_collections - active_collections
    return orphans, qdrant_collections, active_collections


def main():
    dry_run = "--confirm" not in sys.argv

    orphans, all_qdrant, all_active = find_orphans()

    print(f"Total Qdrant collections: {len(all_qdrant)}")
    print(f"Referenced by active chatbots: {len(all_active)}")
    print(f"Orphaned collections found: {len(orphans)}\n")

    if not orphans:
        print("Nothing to clean up.")
        return

    for name in sorted(orphans):
        print(f"  {'[DRY RUN] would delete' if dry_run else 'DELETING'}: {name}")
        if not dry_run:
            try:
                delete_collection(name)
                print(f"    -> deleted")
            except Exception as e:
                print(f"    -> FAILED: {e}")

    if dry_run:
        print("\nThis was a dry run. No collections were deleted.")
        print("Re-run with --confirm to actually delete the orphans listed above.")


if __name__ == "__main__":
    main()