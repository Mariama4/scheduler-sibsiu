from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from functools import wraps
from pymongo import InsertOne, UpdateOne


def singleton(cls):
    instance = None

    @wraps(cls)
    def wrapper(*args, **kwargs):
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance

    return wrapper


@singleton
class MongoDB:
    def __init__(self, username, password, host, port, database):
        self.client = AsyncIOMotorClient(f"mongodb://{username}:{password}@{host}:{port}")
        self.db = self.client[database]

    async def get_all_institutes(self):
        response = await self.db.schedule.distinct('institute_local_name')
        response.sort()
        return response

    async def get_file_names(self, institute_local_name):
        response = self.db.schedule.find({"institute_local_name": institute_local_name},
                                         projection=["file_name"])
        result = []
        async for document in response:
            result.append(document['file_name'])
        result.sort()
        return result

    async def get_document_by_institute_local_name_and_file_name(self,
                                                                 institute_local_name,
                                                                 file_name):
        response = await self.db.schedule.find_one({"institute_local_name": institute_local_name,
                                                    "file_name": file_name})
        return response

    async def upsert_schedule(self, documents, time_limit):
        requests = []
        updated_documents = []
        for document in documents:
            collection_filter = {"file_link": document["file_link"]}
            existing_doc = await self.db.schedule.find_one(collection_filter)

            if existing_doc and float(existing_doc["file_last_modified"]) < document["file_last_modified"]:
                requests.append(
                    UpdateOne(collection_filter,
                              {"$set": {'file_last_modified': document['file_last_modified']}}, upsert=True)
                )
                updated_documents.append(existing_doc)
            elif (existing_doc and existing_doc['timestamp'] +
                  time_limit > datetime.now().timestamp()):
                requests.append(
                    UpdateOne(collection_filter, {"$set": {'timestamp': document['timestamp']}}, upsert=True)
                )
            elif not existing_doc:
                requests.append(
                    InsertOne(document)
                )

        if len(requests) < 1:
            return []

        await self.db.schedule.bulk_write(requests)
        return updated_documents

    async def delete_old_documents(self, time_limit):
        now = datetime.now()
        threshold = (now - timedelta(seconds=time_limit)).timestamp()

        collection_filter = {
            "timestamp": {
                "$lt": threshold
            }
        }

        response = self.db.schedule.find(collection_filter)
        deleted_documents = []
        async for document in response:
            deleted_documents.append(document)

        await self.db.schedule.delete_many(collection_filter)

        return deleted_documents

    async def subscribe_user(self, user_id, document_id):
        collection_filter = {"_id": document_id}
        update = {"$addToSet": {"subscribers": user_id}}

        result = await self.db.schedule.update_one(collection_filter, update)

        return result.modified_count == 1

    async def check_is_user_subscribed(self, user_id, document_id):
        collection_filter = {"_id": document_id}
        document = await self.db.schedule.find_one(collection_filter)
        if 'subscribers' in document:
            if user_id in document['subscribers']:
                return True

        return False

    async def unsubscribe_user(self, user_id, document_id):
        collection_filter = {"_id": document_id}
        update = {"$pull": {"subscribers": user_id}}

        result = await self.db.schedule.update_one(collection_filter, update)

        return result.modified_count == 1

    async def get_document_by_id(self, document_id):
        response = await self.db.schedule.find_one({"_id": document_id})
        return response

    async def get_documents_by_user_id(self, user_id):
        collection_filter = {
            "subscribers": {
                "$in": [user_id]
            }
        }

        # Выполняем запрос к базе данных
        response = self.db.schedule.find(collection_filter)

        result = []
        async for document in response:
            result.append(document)
        result.sort()
        return result

    def close_connection(self):
        self.client.close()
