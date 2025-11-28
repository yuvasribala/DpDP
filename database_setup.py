# database_setup.py
"""
MongoDB Database Setup and Initialization Script for DPDP Compliance System
Run this script to initialize the database with proper collections, indexes, and sample data
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from werkzeug.security import generate_password_hash
from datetime import datetime
import os

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'dpdp_compliance_db'

def setup_database():
    """Initialize MongoDB database with collections and indexes"""
    
    print("🔄 Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    print(f"✅ Connected to database: {DATABASE_NAME}")
    
    # Define collections
    collections = {
        'organizations': db['organizations'],
        'profiles': db['profiles'],
        'assessments': db['assessments'],
        'compliance_reports': db['compliance_reports'],
        'admins': db['admins'],
        'audit_logs': db['audit_logs']
    }
    
    print("\n📊 Creating collections and indexes...")
    
    # Organizations Collection
    print("  └─ Setting up 'organizations' collection...")
    collections['organizations'].create_index([('email', ASCENDING)], unique=True)
    collections['organizations'].create_index([('created_at', DESCENDING)])
    collections['organizations'].create_index([('role', ASCENDING)])
    
    # Profiles Collection
    print("  └─ Setting up 'profiles' collection...")
    collections['profiles'].create_index([('org_id', ASCENDING)], unique=True)
    collections['profiles'].create_index([('is_sdf', ASCENDING)])
    collections['profiles'].create_index([('updated_at', DESCENDING)])
    
    # Assessments Collection
    print("  └─ Setting up 'assessments' collection...")
    collections['assessments'].create_index([('org_id', ASCENDING)])
    collections['assessments'].create_index([('created_at', DESCENDING)])
    collections['assessments'].create_index([('status', ASCENDING)])
    collections['assessments'].create_index([('risk', ASCENDING)])
    
    # Compliance Reports Collection
    print("  └─ Setting up 'compliance_reports' collection...")
    collections['compliance_reports'].create_index([('org_id', ASCENDING)])
    collections['compliance_reports'].create_index([('assessment_id', ASCENDING)])
    collections['compliance_reports'].create_index([('report_date', DESCENDING)])
    collections['compliance_reports'].create_index([('status', ASCENDING)])
    
    # Admins Collection
    print("  └─ Setting up 'admins' collection...")
    collections['admins'].create_index([('email', ASCENDING)], unique=True)
    
    # Audit Logs Collection
    print("  └─ Setting up 'audit_logs' collection...")
    collections['audit_logs'].create_index([('org_id', ASCENDING)])
    collections['audit_logs'].create_index([('action', ASCENDING)])
    collections['audit_logs'].create_index([('timestamp', DESCENDING)])
    
    print("\n✅ All indexes created successfully!")
    
    # Create default admin account
    print("\n👤 Creating default admin account...")
    admin_email = 'admin@dpdp.com'
    admin_password = 'Admin@123'
    
    if not collections['organizations'].find_one({'email': admin_email}):
        admin_doc = {
            'organizationName': 'System Administrator',
            'email': admin_email,
            'phone': '+91-0000000000',
            'gstin': 'ADMIN000000000',
            'password': generate_password_hash(admin_password),
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'verified': True
        }
        collections['organizations'].insert_one(admin_doc)
        print(f"  ✅ Admin account created: {admin_email}")
        print(f"  🔑 Default password: {admin_password}")
        print("  ⚠️  IMPORTANT: Change this password after first login!")
    else:
        print(f"  ℹ️  Admin account already exists: {admin_email}")
    
    # Create sample organization for testing (optional)
    print("\n📝 Creating sample test organization...")
    test_email = 'test@company.com'
    
    if not collections['organizations'].find_one({'email': test_email}):
        test_org = {
            'organizationName': 'Sample Test Company',
            'email': test_email,
            'phone': '+91-9876543210',
            'gstin': '29ABCDE1234F1Z5',
            'password': generate_password_hash('Test@123'),
            'role': 'organization',
            'created_at': datetime.utcnow(),
            'verified': True
        }
        test_result = collections['organizations'].insert_one(test_org)
        print(f"  ✅ Test organization created: {test_email}")
        print(f"  🔑 Password: Test@123")
        
        # Create sample profile for test organization
        test_profile = {
            'org_id': test_result.inserted_id,
            'businessType': 'Technology',
            'employeeCount': '100_to_500',
            'dataVolume': '100k_to_1_million',
            'dataTypes': ['Contact Information', 'Financial Data', 'Health Data'],
            'sensitiveData': 'Yes',
            'dataLocation': 'India',
            'thirdPartySharing': 'Yes',
            'crossBorderTransfer': 'No',
            'sdf_score': 8,
            'is_sdf': False,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        collections['profiles'].insert_one(test_profile)
        print("  ✅ Sample profile created for test organization")
    else:
        print(f"  ℹ️  Test organization already exists: {test_email}")
    
    print("\n" + "="*60)
    print("🎉 Database setup completed successfully!")
    print("="*60)
    
    print("\n📋 Database Summary:")
    print(f"  Database Name: {DATABASE_NAME}")
    print(f"  Collections: {len(collections)}")
    print(f"  Organizations: {collections['organizations'].count_documents({})}")
    print(f"  Profiles: {collections['profiles'].count_documents({})}")
    print(f"  Assessments: {collections['assessments'].count_documents({})}")
    print(f"  Reports: {collections['compliance_reports'].count_documents({})}")
    
    print("\n🔐 Login Credentials:")
    print("  Admin Login:")
    print(f"    Email: admin@dpdp.com")
    print(f"    Password: Admin@123")
    print("\n  Test Organization Login:")
    print(f"    Email: test@company.com")
    print(f"    Password: Test@123")
    
    print("\n🚀 Next Steps:")
    print("  1. Start the Flask application: python app.py")
    print("  2. Access the application at: http://localhost:5000")
    print("  3. Login with credentials above")
    print("  4. ⚠️  Remember to change default passwords in production!")
    
    client.close()

def reset_database():
    """Drop all collections and reset database (USE WITH CAUTION!)"""
    print("⚠️  WARNING: This will delete ALL data from the database!")
    confirmation = input("Type 'DELETE ALL DATA' to confirm: ")
    
    if confirmation == "DELETE ALL DATA":
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        
        print("\n🗑️  Dropping all collections...")
        for collection_name in db.list_collection_names():
            db[collection_name].drop()
            print(f"  ✅ Dropped: {collection_name}")
        
        print("\n✅ Database reset complete!")
        print("Run setup_database() to recreate collections and indexes.")
        client.close()
    else:
        print("❌ Reset cancelled.")

def add_sample_assessments():
    """Add sample assessment data for testing"""
    print("\n📊 Adding sample assessment data...")
    
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    # Find test organization
    test_org = db['organizations'].find_one({'email': 'test@company.com'})
    
    if not test_org:
        print("❌ Test organization not found. Run setup_database() first.")
        return
    
    # Sample assessment answers (50% compliant)
    sample_answers = {
        'q1': 'Yes', 'q2': 'Yes', 'q3': 'Partial', 'q4': 'Yes', 'q5': 'Partial',
        'q6': 'No', 'q7': 'No', 'q8': 'Yes', 'q9': 'Yes', 'q10': 'Partial',
        'q11': 'Yes', 'q12': 'No', 'q13': 'Partial', 'q14': 'No', 'q15': 'Yes',
        'q16': 'No', 'q17': 'No', 'q18': 'No', 'q19': 'Partial', 'q20': 'No',
        'q21': 'Yes', 'q22': 'Yes', 'q23': 'Partial', 'q24': 'No', 'q25': 'Partial'
    }
    
    assessment = {
        'org_id': test_org['_id'],
        'answers': sample_answers,
        'score': 56.5,
        'status': 'Partially Compliant',
        'risk': 'Medium',
        'category_scores': {
            'Consent Management': {'earned': 10.5, 'possible': 13, 'percentage': 80.77},
            'Data Principal Rights': {'earned': 11.0, 'possible': 19, 'percentage': 57.89},
            'Data Security': {'earned': 11.5, 'possible': 14, 'percentage': 82.14}
        },
        'created_at': datetime.utcnow()
    }
    
    result = db['assessments'].insert_one(assessment)
    
    # Create compliance report
    report = {
        'org_id': test_org['_id'],
        'assessment_id': result.inserted_id,
        'organizationName': test_org['organizationName'],
        'score': 56.5,
        'status': 'Partially Compliant',
        'risk': 'Medium',
        'is_sdf': False,
        'sdf_score': 8,
        'recommendations': [
            {
                'action': 'Establish data deletion (Right to be Forgotten) process',
                'category': 'Data Principal Rights',
                'priority': 'High'
            },
            {
                'action': 'Create data breach notification process and templates',
                'category': 'Breach Management',
                'priority': 'High'
            },
            {
                'action': 'Establish incident response plan and team',
                'category': 'Breach Management',
                'priority': 'High'
            }
        ],
        'category_scores': assessment['category_scores'],
        'report_date': datetime.utcnow()
    }
    
    db['compliance_reports'].insert_one(report)
    
    print("✅ Sample assessment and report added successfully!")
    client.close()

def show_database_stats():
    """Display current database statistics"""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    print("\n" + "="*60)
    print("📊 DATABASE STATISTICS")
    print("="*60)
    
    collections = {
        'Organizations': db['organizations'],
        'Profiles': db['profiles'],
        'Assessments': db['assessments'],
        'Reports': db['compliance_reports'],
        'Audit Logs': db['audit_logs']
    }
    
    for name, collection in collections.items():
        count = collection.count_documents({})
        print(f"  {name}: {count} documents")
    
    # Show recent assessments
    print("\n📋 Recent Assessments:")
    recent = db['assessments'].find().sort('created_at', -1).limit(5)
    for idx, assessment in enumerate(recent, 1):
        org = db['organizations'].find_one({'_id': assessment['org_id']})
        print(f"  {idx}. {org['organizationName']} - Score: {assessment['score']}% - {assessment['status']}")
    
    client.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'setup':
            setup_database()
        elif command == 'reset':
            reset_database()
        elif command == 'sample':
            add_sample_assessments()
        elif command == 'stats':
            show_database_stats()
        else:
            print("Unknown command. Use: setup, reset, sample, or stats")
    else:
        # Default action
        print("DPDP Compliance System - Database Setup")
        print("=" * 60)
        print("Available commands:")
        print("  python database_setup.py setup  - Initialize database")
        print("  python database_setup.py reset  - Reset database (deletes all data)")
        print("  python database_setup.py sample - Add sample data")
        print("  python database_setup.py stats  - Show database statistics")
        print("\nRunning default setup...")
        setup_database()