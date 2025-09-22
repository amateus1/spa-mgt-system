import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import uuid
from datetime import datetime

class AWSClient:
    """
    A client to handle all interactions with AWS services (DynamoDB and S3).
    """
    def __init__(self, aws_access_key, aws_secret_key, region_name='us-east-1'):
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.region_name = region_name
        self.dynamodb = None
        self.s3 = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize the AWS service clients."""
        try:
            self.dynamodb = boto3.resource(
                'dynamodb',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region_name
            )
            self.s3 = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region_name
            )
        except NoCredentialsError:
            raise Exception("AWS credentials not available")
    
    def create_members_table(self, table_name='spa-members'):
        """Create the Members table in DynamoDB if it doesn't exist."""
        try:
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{'AttributeName': 'card_id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[{'AttributeName': 'card_id', 'AttributeType': 'S'}],
                BillingMode='PAY_PER_REQUEST'
            )
            table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
            return table
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                return self.dynamodb.Table(table_name)
            raise e
    
    def create_transactions_table(self, table_name='spa-transactions'):
        """Create the Transactions table in DynamoDB if it doesn't exist."""
        try:
            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[{'AttributeName': 'transaction_id', 'KeyType': 'HASH'}],
                AttributeDefinitions=[
                    {'AttributeName': 'transaction_id', 'AttributeType': 'S'},
                    {'AttributeName': 'member_id', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[{
                    'IndexName': 'member_id-index',
                    'KeySchema': [{'AttributeName': 'member_id', 'KeyType': 'HASH'}],
                    'Projection': {'ProjectionType': 'ALL'}
                }],
                BillingMode='PAY_PER_REQUEST'
            )
            table.meta.client.get_waiter('table_exists').wait(TableName=table_name)
            return table
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                return self.dynamodb.Table(table_name)
            raise e
    
    def add_member(self, table, card_id, name, top_up_date, balance):
        """Add a new member to the database."""
        try:
            table.put_item(Item={
                'card_id': card_id,
                'name': name,
                'top_up_date': top_up_date,
                'balance': balance,
                'created_at': datetime.now().isoformat()
            })
            return True
        except ClientError as e:
            print(f"Error adding member: {e}")
            return False
    
    def get_member(self, table, card_id):
        """Retrieve a member by their card ID."""
        try:
            response = table.get_item(Key={'card_id': card_id})
            return response.get('Item', None)
        except ClientError as e:
            print(f"Error getting member: {e}")
            return None
    
    def update_member(self, table, card_id, name, top_up_date, balance):
        """Update a member's information."""
        try:
            table.update_item(
                Key={'card_id': card_id},
                UpdateExpression='SET #n = :name, top_up_date = :date, balance = :balance',
                ExpressionAttributeValues={
                    ':name': name,
                    ':date': top_up_date,
                    ':balance': balance
                },
                ExpressionAttributeNames={'#n': 'name'}
            )
            return True
        except ClientError as e:
            print(f"Error updating member: {e}")
            return False
    
    def delete_member(self, table, card_id):
        """Delete a member from the database."""
        try:
            table.delete_item(Key={'card_id': card_id})
            return True
        except ClientError as e:
            print(f"Error deleting member: {e}")
            return False
    
    def search_members(self, table, search_term):
        """Search for members by card ID or name."""
        try:
            response = table.scan()
            members = response.get('Items', [])
            
            filtered_members = [
                member for member in members 
                if search_term.lower() in member.get('card_id', '').lower() or 
                   search_term.lower() in member.get('name', '').lower()
            ]
            
            return filtered_members
        except ClientError as e:
            print(f"Error searching members: {e}")
            return []
    
    def update_member_balance(self, table, card_id, amount):
        """Update a member's balance by a specified amount."""
        try:
            response = table.update_item(
                Key={'card_id': card_id},
                UpdateExpression='SET balance = balance + :val',
                ExpressionAttributeValues={':val': amount},
                ReturnValues='UPDATED_NEW'
            )
            return response.get('Attributes', {}).get('balance', None)
        except ClientError as e:
            print(f"Error updating balance: {e}")
            return None
    
    def add_transaction(self, table, member_id, amount, signature_key=None, service_notes=None):
        """Add a new transaction record."""
        try:
            transaction_id = str(uuid.uuid4())
            table.put_item(Item={
                'transaction_id': transaction_id,
                'member_id': member_id,
                'amount': amount,
                'timestamp': datetime.now().isoformat(),
                'signature_s3_key': signature_key,
                'service_notes': service_notes
            })
            return transaction_id
        except ClientError as e:
            print(f"Error adding transaction: {e}")
            return None
    
    def get_member_transactions(self, table, member_id):
        """Retrieve all transactions for a specific member."""
        try:
            response = table.query(
                IndexName='member_id-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('member_id').eq(member_id)
            )
            return response.get('Items', [])
        except ClientError as e:
            print(f"Error getting transactions: {e}")
            return []
    
    def upload_signature(self, bucket_name, signature_data, member_id):
        """Process and upload a signature image to S3."""
        try:
            if signature_data.startswith('data:image/png;base64,'):
                signature_data = signature_data.split(',')[1]
            
            import base64
            signature_bytes = base64.b64decode(signature_data)
            
            filename = f"signatures/{member_id}/{uuid.uuid4()}.png"
            
            self.s3.put_object(
                Bucket=bucket_name,
                Key=filename,
                Body=signature_bytes,
                ContentType='image/png'
            )
            
            return filename
        except Exception as e:
            print(f"Error uploading signature: {e}")
            return None