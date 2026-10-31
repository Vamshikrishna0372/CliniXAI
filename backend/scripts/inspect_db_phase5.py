import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["clinixai"]
    docs = await db["documents"].find({}).to_list(100)
    print(f"Total documents found: {len(docs)}")
    for d in docs:
        print(f"ID: {d.get('document_id')} | Patient: {d.get('patient_id')} | Category: {d.get('category')} | Title: {d.get('title')} | MIME: {d.get('mime_type')} | File: {d.get('file_name')} | Deleted: {d.get('is_deleted')}")

if __name__ == "__main__":
    asyncio.run(main())
