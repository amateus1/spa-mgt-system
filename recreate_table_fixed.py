# recreate_table_fixed.py
import boto3
import os
from decimal import Decimal
import uuid
from datetime import datetime

def load_aws_credentials():
    return {
        "AWS_ACCESS_KEY_ID": os.getenv('AWS_ACCESS_KEY_ID'),
        "AWS_SECRET_ACCESS_KEY": os.getenv('AWS_SECRET_ACCESS_KEY'),
        "AWS_REGION": os.getenv('AWS_REGION', 'us-east-1')
    }

def recreate_table():
    print("🔄 Recreating table with correct schema...")
    
    secrets = load_aws_credentials()
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=secrets["AWS_REGION"]
    )
    
    # Delete existing table if it exists
    try:
        table = dynamodb.Table('spa-transactions-v2')
        table.delete()
        print("🗑️  Deleted existing table")
        # Wait for deletion to complete
        import time
        time.sleep(10)
    except Exception as e:
        print(f"ℹ️  No existing table to delete: {e}")
    
    # Create new table with CORRECT schema
    try:
        table = dynamodb.create_table(
            TableName='spa-transactions-v2',
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
        table.meta.client.get_waiter('table_exists').wait(TableName='spa-transactions-v2')
        print("✅ Created new table with correct schema")
        return table
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return None

def migrate_with_correct_schema():
    print("🚀 Starting migration with correct table schema...")
    
    secrets = load_aws_credentials()
    dynamodb = boto3.resource(
        'dynamodb',
        aws_access_key_id=secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=secrets["AWS_REGION"]
    )
    
    # Recreate table
    new_table = recreate_table()
    if not new_table:
        return
    
    # Get old table
    try:
        old_table = dynamodb.Table('spa-transactions')
        print("✅ Connected to old table")
    except Exception as e:
        print(f"❌ Error connecting to old table: {e}")
        return
    
    # Scan old table
    try:
        print("📊 Scanning old table...")
        response = old_table.scan()
        old_items = response.get('Items', [])
        print(f"📋 Found {len(old_items)} transactions")
    except Exception as e:
        print(f"❌ Error scanning: {e}")
        return
    
    # Migrate with CORRECT field names
    migrated_count = 0
    
    for i, item in enumerate(old_items):
        try:
            # Use the EXACT same field names as old table
            new_item = {
                'member_id': item['member_id'],
                'transaction_id': item['transaction_id'],
                'amount': item['amount'],
                'timestamp': item['timestamp'],  # Keep as 'timestamp' not 'transaction_timestamp'
                'service_notes': item.get('service_notes', ''),
                'signature_s3_key': item.get('signature_s3_key')
            }
            
            # Remove None values
            new_item = {k: v for k, v in new_item.items() if v is not None}
            
            new_table.put_item(Item=new_item)
            migrated_count += 1
            print(f"✅ Migrated {i+1}/{len(old_items)}: {item['member_id']} - {item['amount']}")
            
        except Exception as e:
            print(f"❌ Failed {i+1}: {e}")
    
    print(f"\n🎉 Migration complete! {migrated_count}/{len(old_items)} successful")

if __name__ == "__main__":
    migrate_with_correct_schema()