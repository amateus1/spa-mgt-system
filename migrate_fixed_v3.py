# migrate_fixed_v3.py
import boto3
import os
from decimal import Decimal
import uuid
from datetime import datetime

def load_aws_credentials():
    """Load AWS credentials from environment variables"""
    return {
        "AWS_ACCESS_KEY_ID": os.getenv('AWS_ACCESS_KEY_ID'),
        "AWS_SECRET_ACCESS_KEY": os.getenv('AWS_SECRET_ACCESS_KEY'),
        "AWS_REGION": os.getenv('AWS_REGION', 'us-east-1')
    }

class MigrationClient:
    def __init__(self, aws_access_key, aws_secret_key, region_name='us-east-1'):
        self.dynamodb = boto3.resource(
            'dynamodb',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=region_name
        )
    
    def create_new_table(self, table_name='spa-transactions-v2'):
        """Create the new transactions table with correct structure"""
        try:
            # First, check if table already exists
            try:
                existing_table = self.dynamodb.Table(table_name)
                existing_table.load()
                print(f"✅ Using existing table: {table_name}")
                return existing_table
            except:
                pass
            
            # Create new table if it doesn't exist
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'member_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'transaction_id', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'member_id', 'AttributeType': 'S'},
                    {'AttributeName': 'transaction_id', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
            print(f"✅ Created new table: {table_name}")
            return table
        except Exception as e:
            print(f"❌ Error with table: {e}")
            raise

def migrate_transactions():
    """Migrate existing transactions to new table structure"""
    print("🚀 Starting transaction migration...")
    
    # Load credentials
    secrets = load_aws_credentials()
    
    if not secrets["AWS_ACCESS_KEY_ID"]:
        print("❌ AWS credentials not found.")
        return
    
    # Initialize client
    client = MigrationClient(
        secrets["AWS_ACCESS_KEY_ID"],
        secrets["AWS_SECRET_ACCESS_KEY"], 
        secrets["AWS_REGION"]
    )
    
    # Get old table
    try:
        old_table = client.dynamodb.Table('spa-transactions')
        print("✅ Connected to old table: spa-transactions")
    except Exception as e:
        print(f"❌ Error connecting to old table: {e}")
        return
    
    # Create new table
    try:
        new_table = client.create_new_table('spa-transactions-v2')
    except Exception as e:
        print(f"❌ Error creating new table: {e}")
        return
    
    # Scan old table
    try:
        print("📊 Scanning old table for transactions...")
        response = old_table.scan()
        old_items = response.get('Items', [])
        print(f"📋 Found {len(old_items)} transactions to migrate")
        
    except Exception as e:
        print(f"❌ Error scanning old table: {e}")
        return
    
    # Migrate items
    migrated_count = 0
    errors = 0
    
    for i, item in enumerate(old_items):
        try:
            print(f"\n🔄 Processing item {i+1}/{len(old_items)}")
            
            # Extract ALL fields for debugging
            print(f"   Full item: {item}")
            
            # Try to extract member_id - handle null/None case
            member_id = item.get('member_id')
            amount = item.get('amount')
            service_notes = item.get('service_notes')
            signature_s3_key = item.get('signature_s3_key')
            timestamp = item.get('timestamp')
            transaction_id = item.get('transaction_id')
            
            # If member_id is None, try to derive it from other fields or use placeholder
            if member_id is None:
                # Check if we can derive member_id from signature_s3_key
                if signature_s3_key and 'signatures/' in signature_s3_key:
                    # Extract from path like "signatures/00011/2aeeb718..."
                    parts = signature_s3_key.split('/')
                    if len(parts) >= 2:
                        derived_member_id = parts[1]
                        member_id = derived_member_id
                        print(f"   🔍 Derived member_id from signature: {member_id}")
                else:
                    # Use transaction_id as fallback
                    member_id = f"unknown_{transaction_id[:8]}"
                    print(f"   ⚠️  Using generated member_id: {member_id}")
            
            # Validate required fields
            if not transaction_id:
                transaction_id = str(uuid.uuid4())
                print(f"   ⚠️  Generated new transaction_id: {transaction_id}")
            
            # Create new item
            new_item = {
                'member_id': str(member_id),
                'transaction_id': str(transaction_id),
                'amount': Decimal(str(amount)) if amount is not None else Decimal('0'),
                'timestamp': timestamp or datetime.now().isoformat(),
                'signature_s3_key': signature_s3_key,
                'service_notes': service_notes
            }
            
            # Remove None values
            new_item = {k: v for k, v in new_item.items() if v is not None}
            
            # Put item in new table
            new_table.put_item(Item=new_item)
            migrated_count += 1
            print(f"   ✅ Successfully migrated {member_id}: {amount}")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            errors += 1
    
    print("\n🎉 Migration completed!")
    print(f"✅ Successfully migrated: {migrated_count} transactions")
    print(f"❌ Errors encountered: {errors}")
    print(f"📊 Total processed: {len(old_items)}")
    
    # Final verification
    if migrated_count > 0:
        print("\n🔍 Final verification...")
        try:
            # Count items in new table
            response = new_table.scan(Select='COUNT')
            new_count = response['Count']
            print(f"📈 New table now has {new_count} transactions")
            
            # Show all transactions in new table
            sample_response = new_table.scan()
            sample_items = sample_response.get('Items', [])
            print("📝 All transactions in new table:")
            for item in sample_items:
                print(f"   - {item.get('member_id')}: {item.get('amount')} - {item.get('service_notes')}")
                
        except Exception as e:
            print(f"⚠️  Verification failed: {e}")

if __name__ == "__main__":
    migrate_transactions()