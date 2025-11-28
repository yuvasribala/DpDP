# utils.py - Utility functions and helpers
"""
Utility functions for DPDP Compliance System
"""

from datetime import datetime
from bson import ObjectId
import json

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB ObjectId and datetime"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def serialize_mongo_doc(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    
    if isinstance(doc, list):
        return [serialize_mongo_doc(item) for item in doc]
    
    if isinstance(doc, dict):
        result = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = serialize_mongo_doc(value)
            elif isinstance(value, list):
                result[key] = serialize_mongo_doc(value)
            else:
                result[key] = value
        return result
    
    return doc

def validate_email(email):
    """Validate email format"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Validate Indian phone number format"""
    import re
    pattern = r'^\+?91[-\s]?[6-9]\d{9}$'
    return re.match(pattern, phone.replace(' ', '')) is not None

def validate_gstin(gstin):
    """Validate GSTIN format"""
    import re
    pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    return re.match(pattern, gstin) is not None

def calculate_risk_score(assessment_score, sdf_score, data_volume):
    """Calculate overall risk score"""
    risk_score = 0
    
    # Assessment compliance contribution (60%)
    if assessment_score < 50:
        risk_score += 60
    elif assessment_score < 80:
        risk_score += 30
    else:
        risk_score += 10
    
    # SDF status contribution (25%)
    if sdf_score >= 10:
        risk_score += 25
    elif sdf_score >= 7:
        risk_score += 15
    else:
        risk_score += 5
    
    # Data volume contribution (15%)
    volume_risk = {
        'less_than_1k': 2,
        '1k_to_10k': 5,
        '10k_to_100k': 8,
        '100k_to_1_million': 12,
        'more_than_1_million': 15
    }
    risk_score += volume_risk.get(data_volume, 5)
    
    return min(risk_score, 100)

def generate_compliance_certificate(report_data):
    """Generate compliance certificate data"""
    if report_data['score'] >= 80:
        return {
            'eligible': True,
            'certificate_id': f"DPDP-{report_data['org_id'][-8:]}-{datetime.now().strftime('%Y%m')}",
            'valid_until': (datetime.now().replace(year=datetime.now().year + 1)).isoformat(),
            'level': 'Gold' if report_data['score'] >= 90 else 'Silver'
        }
    return {'eligible': False}

# export_data.py - Data export utilities
"""
Export utilities for DPDP Compliance System
"""

import csv
import io
from pymongo import MongoClient
import os

MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
DATABASE_NAME = 'dpdp_compliance_db'

def export_organizations_to_csv():
    """Export all organizations to CSV"""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    organizations = list(db['organizations'].find({'role': 'organization'}))
    
    if not organizations:
        print("No organizations found")
        return
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Organization ID', 'Name', 'Email', 'Phone', 'GSTIN',
        'Registration Date', 'Verified'
    ])
    
    # Data
    for org in organizations:
        writer.writerow([
            str(org['_id']),
            org['organizationName'],
            org['email'],
            org['phone'],
            org['gstin'],
            org['created_at'].strftime('%Y-%m-%d'),
            'Yes' if org.get('verified', False) else 'No'
        ])
    
    # Save to file
    filename = f'organizations_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        f.write(output.getvalue())
    
    print(f"✅ Exported {len(organizations)} organizations to {filename}")
    client.close()

def export_assessments_to_csv():
    """Export all assessments with scores to CSV"""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    assessments = list(db['assessments'].find())
    
    if not assessments:
        print("No assessments found")
        return
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        'Assessment ID', 'Organization', 'Score', 'Status',
        'Risk Level', 'Assessment Date'
    ])
    
    # Data
    for assessment in assessments:
        org = db['organizations'].find_one({'_id': assessment['org_id']})
        writer.writerow([
            str(assessment['_id']),
            org['organizationName'] if org else 'Unknown',
            assessment['score'],
            assessment['status'],
            assessment['risk'],
            assessment['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    # Save to file
    filename = f'assessments_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        f.write(output.getvalue())
    
    print(f"✅ Exported {len(assessments)} assessments to {filename}")
    client.close()

def export_compliance_summary():
    """Generate compliance summary report"""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    total_orgs = db['organizations'].count_documents({'role': 'organization'})
    total_assessments = db['assessments'].count_documents({})
    
    # Compliance statistics
    compliant = db['assessments'].count_documents({'status': 'Fully Compliant'})
    partial = db['assessments'].count_documents({'status': 'Partially Compliant'})
    non_compliant = db['assessments'].count_documents({'status': 'Non-Compliant'})
    
    # SDF statistics
    sdf_count = db['profiles'].count_documents({'is_sdf': True})
    
    # Average score
    pipeline = [{'$group': {'_id': None, 'avg_score': {'$avg': '$score'}}}]
    result = list(db['assessments'].aggregate(pipeline))
    avg_score = result[0]['avg_score'] if result else 0
    
    print("\n" + "="*60)
    print("📊 DPDP COMPLIANCE SUMMARY REPORT")
    print("="*60)
    print(f"\n📈 Overall Statistics:")
    print(f"  Total Organizations: {total_orgs}")
    print(f"  Total Assessments: {total_assessments}")
    print(f"  Average Compliance Score: {avg_score:.2f}%")
    
    print(f"\n✅ Compliance Status Breakdown:")
    print(f"  Fully Compliant: {compliant} ({compliant/total_assessments*100:.1f}%)" if total_assessments > 0 else "  No assessments")
    print(f"  Partially Compliant: {partial} ({partial/total_assessments*100:.1f}%)" if total_assessments > 0 else "")
    print(f"  Non-Compliant: {non_compliant} ({non_compliant/total_assessments*100:.1f}%)" if total_assessments > 0 else "")
    
    print(f"\n🏢 Entity Classification:")
    print(f"  Significant Data Fiduciaries (SDF): {sdf_count}")
    print(f"  Regular Data Fiduciaries: {total_orgs - sdf_count}")
    
    # Recent assessments
    print(f"\n📅 Recent Assessments (Last 5):")
    recent = db['assessments'].find().sort('created_at', -1).limit(5)
    for idx, assessment in enumerate(recent, 1):
        org = db['organizations'].find_one({'_id': assessment['org_id']})
        print(f"  {idx}. {org['organizationName']} - {assessment['score']:.1f}% - {assessment['status']}")
    
    client.close()

# backup_restore.py - Backup and restore utilities
"""
Backup and restore utilities for DPDP Compliance System
"""

import json
from datetime import datetime

def backup_database():
    """Create backup of entire database"""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    backup_data = {
        'backup_date': datetime.now().isoformat(),
        'database': DATABASE_NAME,
        'collections': {}
    }
    
    collections = ['organizations', 'profiles', 'assessments', 'compliance_reports']
    
    print("🔄 Creating database backup...")
    
    for col_name in collections:
        documents = list(db[col_name].find())
        backup_data['collections'][col_name] = [
            serialize_mongo_doc(doc) for doc in documents
        ]
        print(f"  ✅ Backed up {len(documents)} documents from '{col_name}'")
    
    filename = f'dpdp_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, cls=MongoJSONEncoder)
    
    print(f"\n✅ Backup completed: {filename}")
    print(f"   Size: {os.path.getsize(filename) / 1024:.2f} KB")
    
    client.close()
    return filename

def restore_database(backup_file):
    """Restore database from backup file"""
    if not os.path.exists(backup_file):
        print(f"❌ Backup file not found: {backup_file}")
        return
    
    print("⚠️  WARNING: This will replace existing data!")
    confirmation = input("Type 'RESTORE' to confirm: ")
    
    if confirmation != 'RESTORE':
        print("❌ Restore cancelled")
        return
    
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    with open(backup_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    print(f"\n🔄 Restoring from backup: {backup_data['backup_date']}")
    
    for col_name, documents in backup_data['collections'].items():
        # Clear existing data
        db[col_name].delete_many({})
        
        # Insert backup data
        if documents:
            # Convert string IDs back to ObjectId
            for doc in documents:
                if '_id' in doc and isinstance(doc['_id'], str):
                    doc['_id'] = ObjectId(doc['_id'])
                if 'org_id' in doc and isinstance(doc['org_id'], str):
                    doc['org_id'] = ObjectId(doc['org_id'])
                if 'assessment_id' in doc and isinstance(doc['assessment_id'], str):
                    doc['assessment_id'] = ObjectId(doc['assessment_id'])
            
            db[col_name].insert_many(documents)
        
        print(f"  ✅ Restored {len(documents)} documents to '{col_name}'")
    
    print("\n✅ Database restore completed!")
    client.close()

# admin_tools.py - Administrative tools
"""
Administrative tools for DPDP Compliance System
"""

def reset_organization_password(email, new_password):
    """Reset password for an organization"""
    from werkzeug.security import generate_password_hash
    
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    result = db['organizations'].update_one(
        {'email': email},
        {'$set': {'password': generate_password_hash(new_password)}}
    )
    
    if result.modified_count > 0:
        print(f"✅ Password reset successful for {email}")
    else:
        print(f"❌ Organization not found: {email}")
    
    client.close()

def delete_organization(email):
    """Delete organization and all related data"""
    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]
    
    org = db['organizations'].find_one({'email': email})
    
    if not org:
        print(f"❌ Organization not found: {email}")
        return
    
    print(f"⚠️  WARNING: This will delete all data for {org['organizationName']}")
    confirmation = input("Type 'DELETE' to confirm: ")
    
    if confirmation != 'DELETE':
        print("❌ Deletion cancelled")
        return
    
    org_id = org['_id']
    
    # Delete from all collections
    db['organizations'].delete_one({'_id': org_id})
    db['profiles'].delete_many({'org_id': org_id})
    db['assessments'].delete_many({'org_id': org_id})
    db['compliance_reports'].delete_many({'org_id': org_id})
    
    print(f"✅ Successfully deleted organization: {email}")
    client.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Available commands:")
        print("  python utils.py export_orgs      - Export organizations to CSV")
        print("  python utils.py export_assess    - Export assessments to CSV")
        print("  python utils.py summary          - Show compliance summary")
        print("  python utils.py backup           - Create database backup")
        print("  python utils.py restore <file>   - Restore from backup")
        print("  python utils.py reset_pass <email> <new_pass> - Reset password")
        print("  python utils.py delete_org <email> - Delete organization")
    else:
        command = sys.argv[1]
        
        if command == 'export_orgs':
            export_organizations_to_csv()
        elif command == 'export_assess':
            export_assessments_to_csv()
        elif command == 'summary':
            export_compliance_summary()
        elif command == 'backup':
            backup_database()
        elif command == 'restore' and len(sys.argv) > 2:
            restore_database(sys.argv[2])
        elif command == 'reset_pass' and len(sys.argv) > 3:
            reset_organization_password(sys.argv[2], sys.argv[3])
        elif command == 'delete_org' and len(sys.argv) > 2:
            delete_organization(sys.argv[2])
        else:
            print("Invalid command or missing arguments")