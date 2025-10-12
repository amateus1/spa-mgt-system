# migrate_transactions.py
import boto3
from aws_utils import AWSClient
import os
from decimal import Decimal
import streamlit as st

def load_streamlit_secrets():
    """Load secrets similar to how Streamlit does it"""
    # You'll need to set these as environment variables or modify for your setup
    return {
        "AWS_ACCESS_KEY_ID": os.getenv('AWS_ACCESS_KEY_ID'),
        "AWS_SECRET_ACCESS_KEY": os.getenv('AWS_SECRET_ACCESS_KEY'),
        "AWS_REGION": os.getenv('AWS_REGION', 'us-east-1')
    }

def migrate_transactions():
    """Migrate existing transactions to new table structure"""
    print("🚀 Starting transaction migration...")
    
    # Load credentials
    secrets = load_streamlit_secrets()
    
    if not secrets["AWS_ACCESS_KEY_ID"]:
        print("❌ AWS credentials not found. Please set environment variables:")
        print("   export AWS_ACCESS_KEY_ID=your_access_key")
        print("   export AWS_SECRET_ACCESS_KEY=your_secret_key")
        return
    
    # Initialize AWS client
    client = AWSClient(
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
        new_table = client.create_transactions_table('spa-transactions-v2')
        print("✅ Created/connected to new table: spa-transactions-v2")
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
    
    for item in old_items:
        try:
            # Ensure we have required fields
            member_id = item.get('member_id')
            transaction_id = item.get('transaction_id')
            
            if not member_id or not transaction_id:
                print(f"⚠️  Skipping item missing required fields: {item}")
                errors += 1
                continue
                
            # Copy to new table with proper structure
            new_item = {
                'member_id': member_id,
                'transaction_id': transaction_id,
                'amount': item.get('amount', Decimal('0')),
                'timestamp': item.get('timestamp', ''),
                'signature_s3_key': item.get('signature_s3_key'),
                'service_notes': item.get('service_notes')
            }
            
            # Remove None values to avoid DynamoDB errors
            new_item = {k: v for k, v in new_item.items() if v is not None}
            
            new_table.put_item(Item=new_item)
            migrated_count += 1
            
            if migrated_count % 10 == 0:
                print(f"📦 Migrated {migrated_count} transactions...")
                
        except Exception as e:
            print(f"❌ Error migrating item {item.get('transaction_id', 'unknown')}: {e}")
            errors += 1
    
    print("\n🎉 Migration completed!")
    print(f"✅ Successfully migrated: {migrated_count} transactions")
    print(f"❌ Errors encountered: {errors}")
    print(f"📊 Total processed: {len(old_items)}")
    
    # Verify migration
    if migrated_count > 0:
        print("\n🔍 Verifying migration...")
        try:
            # Check one member to verify
            sample_response = new_table.scan(Limit=5)
            sample_items = sample_response.get('Items', [])
            print(f"📝 Sample of new table records: {len(sample_items)}")
            for item in sample_items:
                print(f"   - {item.get('member_id')}: {item.get('amount')}")
        except Exception as e:
            print(f"⚠️  Verification check failed: {e}")

if __name__ == "__main__":
    migrate_transactions()