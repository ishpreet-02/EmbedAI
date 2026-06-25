from services.database import get_supabase
db = get_supabase()
r = db.table("chatbots").select("id,name,status,pages_indexed").execute()
for c in r.data:
    print(f'{c["name"]}: status={c["status"]}, pages={c["pages_indexed"]}')
