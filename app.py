from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import os
import secrets
from functools import wraps
import io
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
CORS(app)

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['dpdp_compliance_db']

# Collections
organizations_col = db['organizations']
profiles_col = db['profiles']
assessments_col = db['assessments']
reports_col = db['compliance_reports']
admins_col = db['admins']

# Create indexes
organizations_col.create_index('email', unique=True)
profiles_col.create_index('org_id')
assessments_col.create_index('org_id')
reports_col.create_index('org_id')

# JWT Token Helper
def generate_token(org_id, email):
    payload = {
        'org_id': str(org_id),
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_org = organizations_col.find_one({'_id': ObjectId(data['org_id'])})
            if not current_org:
                return jsonify({'message': 'Invalid token'}), 401
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        return f(current_org, *args, **kwargs)
    return decorated

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['organizationName', 'email', 'phone', 'gstin', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if organization already exists
        if organizations_col.find_one({'email': data['email']}):
            return jsonify({'error': 'Organization already registered with this email'}), 400
        
        # Hash password
        hashed_password = generate_password_hash(data['password'])
        
        # Create organization document
        org_doc = {
            'organizationName': data['organizationName'],
            'email': data['email'],
            'phone': data['phone'],
            'gstin': data['gstin'],
            'password': hashed_password,
            'created_at': datetime.utcnow(),
            'verified': False,
            'role': 'organization'
        }
        
        result = organizations_col.insert_one(org_doc)
        org_id = result.inserted_id
        
        # Generate token
        token = generate_token(org_id, data['email'])
        
        return jsonify({
            'message': 'Registration successful',
            'token': token,
            'org_id': str(org_id),
            'organizationName': data['organizationName']
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        org = organizations_col.find_one({'email': email})
        
        if not org or not check_password_hash(org['password'], password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        token = generate_token(org['_id'], email)
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'org_id': str(org['_id']),
            'organizationName': org['organizationName']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/profile', methods=['POST'])
@token_required
def save_profile(current_org):
    try:
        data = request.json
        org_id = current_org['_id']
        
        # Calculate SDF score
        sdf_score = calculate_sdf_score(data)
        is_sdf = sdf_score >= 10
        
        profile_doc = {
            'org_id': org_id,
            'businessType': data.get('businessType'),
            'employeeCount': data.get('employeeCount'),
            'dataVolume': data.get('dataVolume'),
            'dataTypes': data.get('dataTypes', []),
            'sensitiveData': data.get('sensitiveData'),
            'dataLocation': data.get('dataLocation'),
            'thirdPartySharing': data.get('thirdPartySharing'),
            'crossBorderTransfer': data.get('crossBorderTransfer'),
            'sdf_score': sdf_score,
            'is_sdf': is_sdf,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        # Update or insert profile
        profiles_col.update_one(
            {'org_id': org_id},
            {'$set': profile_doc},
            upsert=True
        )
        
        return jsonify({
            'message': 'Profile saved successfully',
            'sdf_score': sdf_score,
            'is_sdf': is_sdf
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/assessment', methods=['POST'])
@token_required
def submit_assessment(current_org):
    try:
        data = request.json
        org_id = current_org['_id']
        answers = data.get('answers', {})
        
        # Calculate compliance score
        score_result = calculate_compliance_score(answers)
        
        # Generate recommendations
        recommendations = generate_recommendations(answers, score_result)
        
        # Determine status and risk
        score = score_result['percentage']
        if score >= 80:
            status = 'Fully Compliant'
            risk = 'Low'
        elif score >= 50:
            status = 'Partially Compliant'
            risk = 'Medium'
        else:
            status = 'Non-Compliant'
            risk = 'High'
        
        # Get profile for SDF info
        profile = profiles_col.find_one({'org_id': org_id})
        
        assessment_doc = {
            'org_id': org_id,
            'answers': answers,
            'score': score,
            'status': status,
            'risk': risk,
            'category_scores': score_result['category_scores'],
            'created_at': datetime.utcnow()
        }
        
        assessment_result = assessments_col.insert_one(assessment_doc)
        
        # Create compliance report
        report_doc = {
            'org_id': org_id,
            'assessment_id': assessment_result.inserted_id,
            'organizationName': current_org['organizationName'],
            'score': score,
            'status': status,
            'risk': risk,
            'is_sdf': profile['is_sdf'] if profile else False,
            'sdf_score': profile['sdf_score'] if profile else 0,
            'recommendations': recommendations,
            'category_scores': score_result['category_scores'],
            'report_date': datetime.utcnow()
        }
        
        report_result = reports_col.insert_one(report_doc)
        
        return jsonify({
            'message': 'Assessment submitted successfully',
            'assessment_id': str(assessment_result.inserted_id),
            'report_id': str(report_result.inserted_id),
            'score': score,
            'status': status,
            'risk': risk
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report/<report_id>', methods=['GET'])
@token_required
def get_report(current_org, report_id):
    try:
        report = reports_col.find_one({
            '_id': ObjectId(report_id),
            'org_id': current_org['_id']
        })
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # Convert ObjectId to string
        report['_id'] = str(report['_id'])
        report['org_id'] = str(report['org_id'])
        report['assessment_id'] = str(report['assessment_id'])
        report['report_date'] = report['report_date'].isoformat()
        
        return jsonify(report), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report/<report_id>/pdf', methods=['GET'])
@token_required
def download_report_pdf(current_org, report_id):
    try:
        report = reports_col.find_one({
            '_id': ObjectId(report_id),
            'org_id': current_org['_id']
        })
        
        if not report:
            return jsonify({'error': 'Report not found'}), 404
        
        # Generate PDF
        pdf_buffer = generate_pdf_report(report)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'DPDP_Compliance_Report_{report_id}.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/organizations', methods=['GET'])
@token_required
def admin_get_organizations(current_org):
    try:
        # Check if user is admin
        if current_org.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        orgs = list(organizations_col.find({'role': 'organization'}))
        
        result = []
        for org in orgs:
            # Get latest assessment
            latest_assessment = assessments_col.find_one(
                {'org_id': org['_id']},
                sort=[('created_at', -1)]
            )
            
            org_data = {
                'id': str(org['_id']),
                'organizationName': org['organizationName'],
                'email': org['email'],
                'phone': org['phone'],
                'gstin': org['gstin'],
                'created_at': org['created_at'].isoformat(),
                'last_assessment': latest_assessment['created_at'].isoformat() if latest_assessment else None,
                'compliance_score': latest_assessment['score'] if latest_assessment else None,
                'status': latest_assessment['status'] if latest_assessment else 'Not Assessed'
            }
            result.append(org_data)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Helper Functions
def calculate_sdf_score(profile_data):
    score = 0
    
    # Data volume scoring
    volume = profile_data.get('dataVolume', '')
    if volume == 'more_than_1_million':
        score += 5
    elif volume == '100k_to_1_million':
        score += 3
    elif volume == '10k_to_100k':
        score += 2
    
    # Employee count
    employees = profile_data.get('employeeCount', '')
    if employees == 'more_than_500':
        score += 3
    elif employees == '100_to_500':
        score += 2
    
    # Sensitive data
    if profile_data.get('sensitiveData') == 'Yes':
        score += 4
    
    # Data types - check for children data
    data_types = profile_data.get('dataTypes', [])
    if 'Children Data' in data_types:
        score += 5
    
    # Cross-border transfer
    if profile_data.get('crossBorderTransfer') == 'Yes':
        score += 3
    
    return score

def calculate_compliance_score(answers):
    questions = get_assessment_questions()
    total_possible = 0
    total_earned = 0
    category_scores = {}
    
    for q in questions:
        q_id = q['id']
        weight = q['weight']
        category = q['category']
        
        if category not in category_scores:
            category_scores[category] = {'earned': 0, 'possible': 0}
        
        total_possible += weight
        category_scores[category]['possible'] += weight
        
        answer = answers.get(q_id, 'No')
        if answer == 'Yes':
            earned = weight
        elif answer == 'Partial':
            earned = weight * 0.5
        else:
            earned = 0
        
        total_earned += earned
        category_scores[category]['earned'] += earned
    
    # Calculate percentages
    percentage = (total_earned / total_possible * 100) if total_possible > 0 else 0
    
    for cat in category_scores:
        possible = category_scores[cat]['possible']
        earned = category_scores[cat]['earned']
        category_scores[cat]['percentage'] = (earned / possible * 100) if possible > 0 else 0
    
    return {
        'percentage': round(percentage, 2),
        'total_earned': total_earned,
        'total_possible': total_possible,
        'category_scores': category_scores
    }

def generate_recommendations(answers, score_result):
    recommendations = []
    priority_map = {'High': 1, 'Medium': 2, 'Low': 3}
    
    # Check each question and generate recommendations
    questions = get_assessment_questions()
    
    for q in questions:
        answer = answers.get(q['id'], 'No')
        if answer != 'Yes':
            priority = 'High' if answer == 'No' else 'Medium'
            recommendations.append({
                'action': q['recommendation'],
                'category': q['category'],
                'priority': priority
            })
    
    # Sort by priority
    recommendations.sort(key=lambda x: priority_map[x['priority']])
    
    # Return top 10
    return recommendations[:10]

def get_assessment_questions():
    return [
        {'id': 'q1', 'category': 'Consent Management', 'weight': 5, 
         'recommendation': 'Implement explicit consent mechanism before collecting personal data'},
        {'id': 'q2', 'category': 'Consent Management', 'weight': 4,
         'recommendation': 'Create clear, accessible privacy notice explaining data usage'},
        {'id': 'q3', 'category': 'Consent Management', 'weight': 4,
         'recommendation': 'Implement consent withdrawal mechanism'},
        {'id': 'q4', 'category': 'Data Principal Rights', 'weight': 5,
         'recommendation': 'Create data access request fulfillment process'},
        {'id': 'q5', 'category': 'Data Principal Rights', 'weight': 5,
         'recommendation': 'Implement data correction and updation process'},
        {'id': 'q6', 'category': 'Data Principal Rights', 'weight': 5,
         'recommendation': 'Establish data deletion (Right to be Forgotten) process'},
        {'id': 'q7', 'category': 'Data Principal Rights', 'weight': 4,
         'recommendation': 'Create data portability mechanism'},
        {'id': 'q8', 'category': 'Data Security', 'weight': 5,
         'recommendation': 'Implement encryption for sensitive data storage'},
        {'id': 'q9', 'category': 'Data Security', 'weight': 5,
         'recommendation': 'Establish access control and authentication systems'},
        {'id': 'q10', 'category': 'Data Security', 'weight': 4,
         'recommendation': 'Conduct regular security audits and vulnerability assessments'},
        {'id': 'q11', 'category': 'Data Retention', 'weight': 4,
         'recommendation': 'Define and document data retention policies'},
        {'id': 'q12', 'category': 'Data Retention', 'weight': 4,
         'recommendation': 'Implement automated data deletion after retention period'},
        {'id': 'q13', 'category': 'Data Processing', 'weight': 4,
         'recommendation': 'Establish Data Processing Agreements with all processors'},
        {'id': 'q14', 'category': 'Data Processing', 'weight': 3,
         'recommendation': 'Implement processor audit and compliance verification'},
        {'id': 'q15', 'category': 'Children Data', 'weight': 5,
         'recommendation': 'Implement parental consent mechanism for children\'s data'},
        {'id': 'q16', 'category': 'Breach Management', 'weight': 5,
         'recommendation': 'Create data breach notification process and templates'},
        {'id': 'q17', 'category': 'Breach Management', 'weight': 5,
         'recommendation': 'Establish incident response plan and team'},
        {'id': 'q18', 'category': 'Governance', 'weight': 5,
         'recommendation': 'Appoint Data Protection Officer (mandatory for SDF)'},
        {'id': 'q19', 'category': 'Governance', 'weight': 4,
         'recommendation': 'Maintain comprehensive data processing records'},
        {'id': 'q20', 'category': 'Governance', 'weight': 4,
         'recommendation': 'Conduct Data Protection Impact Assessments for high-risk processing'},
        {'id': 'q21', 'category': 'Cross-border Transfer', 'weight': 4,
         'recommendation': 'Ensure adequate safeguards for international data transfers'},
        {'id': 'q22', 'category': 'Transparency', 'weight': 3,
         'recommendation': 'Publish and regularly update privacy policy'},
        {'id': 'q23', 'category': 'Accountability', 'weight': 4,
         'recommendation': 'Implement data protection compliance monitoring system'},
        {'id': 'q24', 'category': 'Training', 'weight': 3,
         'recommendation': 'Conduct regular employee training on DPDP compliance'},
        {'id': 'q25', 'category': 'Compliance', 'weight': 4,
         'recommendation': 'Establish grievance redressal mechanism for data principals'}
    ]

def generate_pdf_report(report):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=30,
        alignment=1
    )
    
    elements.append(Paragraph("DPDP Compliance Assessment Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Organization Info
    org_data = [
        ['Organization Name:', report['organizationName']],
        ['Report Date:', report['report_date'].strftime('%Y-%m-%d %H:%M:%S')],
        ['Report ID:', str(report['_id'])]
    ]
    
    org_table = Table(org_data, colWidths=[2*inch, 4*inch])
    org_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(org_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Compliance Score Section
    score_color = colors.green if report['score'] >= 80 else colors.orange if report['score'] >= 50 else colors.red
    
    score_data = [
        ['Compliance Score:', f"{report['score']}%"],
        ['Status:', report['status']],
        ['Risk Level:', report['risk']],
        ['Entity Classification:', 'Significant Data Fiduciary' if report['is_sdf'] else 'Data Fiduciary']
    ]
    
    score_table = Table(score_data, colWidths=[2*inch, 4*inch])
    score_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('TEXTCOLOR', (1, 0), (1, 0), score_color),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f4f6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(score_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Recommendations
    elements.append(Paragraph("Priority Remediation Actions", styles['Heading2']))
    elements.append(Spacer(1, 0.1*inch))
    
    rec_data = [['Priority', 'Category', 'Recommended Action']]
    for rec in report['recommendations']:
        rec_data.append([rec['priority'], rec['category'], rec['action']])
    
    rec_table = Table(rec_data, colWidths=[1*inch, 1.5*inch, 3.5*inch])
    rec_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')])
    ]))
    
    elements.append(rec_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

if __name__ == '__main__':
    # Ensure default admin exists (idempotent creation)
    admin_email = 'admin@dpdp.com'
    admin_password = 'admin123'  # or change if you want

    # Create admin organization only if it doesn't exist
    if not organizations_col.find_one({'email': admin_email}):
        organizations_col.insert_one({
            'organizationName': 'System Admin',
            'email': admin_email,
            'phone': '0000000000',
            'gstin': 'ADMIN000000',
            'password': generate_password_hash(admin_password),
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'verified': True
        })

    # Create admin entry in admins collection only if it doesn't exist
    if not admins_col.find_one({'email': admin_email}):
        admins_col.insert_one({
            'email': admin_email,
            'password': generate_password_hash(admin_password),
            'role': 'admin',
            'created_at': datetime.utcnow()
        })

    app.run(debug=True, host='0.0.0.0', port=5000)
