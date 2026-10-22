import os, re, sys
os.environ["DATABASE_URL"]="sqlite:///./test_email_flow.db"
os.environ["SMTP_HOST"]=""
os.environ["EMAIL_WORKER_ENABLED"]="false"
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), ".."))
from datetime import datetime, timedelta, date, time
from fastapi.testclient import TestClient
from app.database import Base, engine, SessionLocal
import app.models
from app.models import *
from app.models.org import Permission, Role, Shift, Department, Position, EmploymentType, role_permissions
from app.models.email import EmailQueue
from app.models.people import Employee, User
from app.core import security, config
from app.main import app
from app.services import email_worker, email_service
from app.core import email as core_email

Base.metadata.create_all(engine)
db=SessionLocal()
perms=["manage_employees","assign_roles","edit_employee_assignment","approve_leave","approve_overtime","view_reports","self_checkin","apply_leave"]
P={n:Permission(permission_name=n,description=n) for n in perms}
R={n:Role(role_name=n,description=n) for n in ["Admin","HR","Manager","Employee"]}
db.add_all(list(P.values())+list(R.values())); db.flush()
grant={"Admin":perms,"HR":perms,"Manager":["edit_employee_assignment","approve_leave","approve_overtime","view_reports","self_checkin","apply_leave"],"Employee":["self_checkin","apply_leave"]}
for r,ps in grant.items():
    for n in ps: db.execute(role_permissions.insert().values(role_id=R[r].role_id,permission_id=P[n].permission_id))
d=Department(department_name="Eng"); db.add(d); db.flush(); pos=Position(title="Dev",department_id=d.department_id); et=EmploymentType(type_name="Full"); 
sh=Shift(shift_name="S",start_time=time(9),end_time=time(18),late_cutoff=time(0,0,1),min_half_day_hours=4,max_ot_hours_per_day=2,requires_ot_approval=1)
sh2=Shift(shift_name="NoApproval",start_time=time(9),end_time=time(18),late_cutoff=time(23,59),min_half_day_hours=4,max_ot_hours_per_day=2,requires_ot_approval=0)
from app.models.leave import LeaveType
lt=LeaveType(type_name="Casual Leave",max_days_per_year=12)
db.add_all([d,pos,et,sh,sh2,lt]); db.flush()
def mk(name,role,personal,mgr=None,shift=sh):
    e=Employee(full_name=name,email=name.lower().replace(" ",".")+"@meridian.com",personal_email=personal,date_joined=date(2024,1,1),department_id=d.department_id,position_id=pos.position_id,employment_type_id=et.employment_type_id,shift_id=shift.shift_id,manager_id=mgr)
    db.add(e); db.flush()
    u=User(employee_id=e.employee_id,username=e.email.split("@")[0],email=e.email,password_hash=security.hash_password("Pass@1234"),role_id=R[role].role_id,role_name=role,must_reset_password=0,is_active=1)
    db.add(u); db.flush(); return e,u
adm_e,adm_u=mk("Admin One","Admin","admin@gmail.com")
hr_e,hr_u=mk("Hana HR","HR","hr@gmail.com")
mgr_e,mgr_u=mk("Mina Manager","Manager","mgr@gmail.com")
emp_e,emp_u=mk("Eve Employee","Employee","eve@gmail.com",mgr=mgr_e.employee_id)
solo_e,solo_u=mk("Sam Solo","Employee","sam@gmail.com")   # no manager
db.commit()

c=TestClient(app)
def login(email,pw="Pass@1234"):
    r=c.post("/api/auth/login",json={"email":email,"password":pw}); assert r.status_code==200,r.text
    return {"Authorization":"Bearer "+r.json()["access_token"]}
A=login(adm_u.email); H=login(hr_u.email); M=login(mgr_u.email); E=login(emp_u.email); S=login(solo_u.email)

def run_worker():
    d2=SessionLocal(); n=email_worker.process_due_emails(d2); d2.close(); return n
def mails(**f):
    d2=SessionLocal(); q=d2.query(EmailQueue)
    for k,v in f.items(): q=q.filter(getattr(EmailQueue,k)==v)
    rows=q.order_by(EmailQueue.email_id).all(); d2.close(); return rows
ok=lambda m: print("PASS",m)

# capture the link BEFORE the worker redacts the body
body={"full_name":"Nina New","department_id":d.department_id,"position_id":pos.position_id,"employment_type_id":et.employment_type_id,"shift_id":sh.shift_id,"date_joined":"2025-01-01","role_name":"Manager","personal_email":"nina@gmail.com"}
r=c.post("/api/employees",json=body,headers=A); assert r.status_code==201,r.text
j=r.json(); assert "temporary_password" not in j and j["invitation_queued"] and j["personal_email"]=="nina@gmail.com"; ok("1 create user -> invitation queued, no password in response")
inv=mails(category="invitation"); assert len(inv)==1 and inv[0].to_address=="nina@gmail.com" and inv[0].status=="Pending"
link=re.search(r"http://\S+/setup-password\?token=\S+",inv[0].body).group(0)
token=link.split("token=")[1]
u=SessionLocal().query(User).filter(User.email==j["email"]).first()
assert u.setup_token_hash==security.hash_setup_token(token) and token not in (u.setup_token_hash); ok("2 only token HASH stored")
assert run_worker()==1; inv=mails(category="invitation")[0]; assert inv.status=="Sent" and "removed" in inv.body; ok("3 worker sent (simulated) and wiped link from body")

# validation: company-domain personal email, duplicate, HR creating Admin
b2=dict(body,personal_email="x@meridian.com"); assert c.post("/api/employees",json=b2,headers=A).status_code==422; ok("4 company-domain personal email rejected")
b3=dict(body,full_name="Other Person"); assert c.post("/api/employees",json=b3,headers=A).status_code==409; ok("5 duplicate personal email rejected (409)")
b4=dict(body,full_name="Evil Admin",role_name="Admin",personal_email="evil@gmail.com"); assert c.post("/api/employees",json=b4,headers=H).status_code==403; ok("6 HR cannot create Admin (403)")
assert len(mails(category="invitation"))==1; ok("6b no invitation queued on failed create")

# setup page + token use
assert c.get("/setup-password?token="+token).status_code==200
assert c.get("/api/auth/setup-password/check",params={"token":token}).json()["valid"]; ok("7 setup page + check")
bad=c.post("/api/auth/setup-password",json={"token":token,"new_password":"weak","confirm_password":"weak"}); assert bad.status_code==422
assert c.post("/api/auth/setup-password",json={"token":token,"new_password":"Newpass@123","confirm_password":"Nope@123"}).status_code==422
r=c.post("/api/auth/setup-password",json={"token":token,"new_password":"Newpass@123","confirm_password":"Newpass@123"}); assert r.status_code==200,r.text
lg=c.post("/api/auth/login",json={"email":j["email"],"password":"Newpass@123"}); assert lg.status_code==200 and lg.json()["must_reset_password"] is False; ok("8 set password via link, can log in, no forced reset")
assert c.post("/api/auth/setup-password",json={"token":token,"new_password":"Another@123","confirm_password":"Another@123"}).status_code==400; ok("9 link cannot be reused")
assert c.post("/api/auth/setup-password",json={"token":"garbage","new_password":"Another@123","confirm_password":"Another@123"}).status_code==400

# resend + expiry
emp_id=u.employee_id
assert c.post(f"/api/employees/{emp_id}/resend-invitation",headers=A).status_code==400; ok("10 resend refused after password set")
b5=dict(body,full_name="Olga Late",role_name="Employee",personal_email="olga@gmail.com"); r=c.post("/api/employees",json=b5,headers=H); assert r.status_code==201
olga=SessionLocal().query(User).filter(User.email==r.json()["email"]).first()
t1=re.search(r"token=(\S+)",mails(to_address="olga@gmail.com")[0].body).group(1)
d3=SessionLocal(); uo=d3.query(User).get(olga.user_id); uo.setup_token_expiry=datetime.utcnow()-timedelta(hours=1); d3.commit(); d3.close()
assert c.get("/api/auth/setup-password/check",params={"token":t1}).status_code==400; ok("11 expired link rejected")
assert c.post(f"/api/employees/{olga.employee_id}/resend-invitation",headers=H).status_code==200
t2=re.search(r"token=(\S+)",mails(to_address="olga@gmail.com")[-1].body).group(1); assert t2!=t1
assert c.get("/api/auth/setup-password/check",params={"token":t2}).status_code==200
assert c.get("/api/auth/setup-password/check",params={"token":t1}).status_code==400; ok("12 resend -> new link works, old link dead")
assert c.post(f"/api/employees/{adm_e.employee_id}/resend-invitation",headers=H).status_code in (400,403); ok("13 HR cannot resend for Admin")
run_worker()

# leave: employee with manager
def clear(): 
    d2=SessionLocal(); [x.__class__ for x in []]; run_worker()
lv={"leave_type_id":lt.leave_type_id,"start_date":"2026-11-02","end_date":"2026-11-03","reason":"Family"}
n0=len(mails()); r=c.post("/api/leave-requests",json=lv,headers=E); assert r.status_code==201,r.text; lid=r.json()["leave_request_id"]
new=mails()[n0:]; assert [m.to_address for m in new]==["mgr@gmail.com"] and new[0].template=="new_request" and "Eve Employee" in new[0].subject; ok("14 leave apply -> manager emailed (at personal address)")
n0=len(mails()); assert c.put(f"/api/leave-requests/{lid}/decision",json={"approve":False},headers=M).status_code==200
new=mails()[n0:]; assert [m.to_address for m in new]==["eve@gmail.com"] and "rejected" in new[0].subject; ok("15 reject -> employee emailed")
# self-approval blocked, no email
r=c.post("/api/leave-requests",json=lv,headers=M); mlid=r.json()["leave_request_id"]; n0=len(mails())
assert c.put(f"/api/leave-requests/{mlid}/decision",json={"approve":True},headers=M).status_code==403 and len(mails())==n0; ok("16 self-approval still blocked, no email")
# manager's own leave has no manager -> HR
assert "hr@gmail.com" in [m.to_address for m in mails() if m.template=="new_request"]; ok("17 manager w/o manager -> HR gets request email")
# solo employee -> HR ; HR applicant -> Admin
n0=len(mails()); c.post("/api/leave-requests",json=lv,headers=H); assert [m.to_address for m in mails()[n0:]]==["admin@gmail.com"]; ok("18 HR applicant -> Admin emailed (not self)")
# approve leave
n0=len(mails()); assert c.put(f"/api/leave-requests/{lid+0}/decision",json={"approve":True},headers=A).status_code==200
assert mails()[-1].to_address=="eve@gmail.com" and "approved" in mails()[-1].subject; ok("19 approve -> employee emailed")

# overtime
n0=len(mails()); r=c.post("/api/overtime",json={"work_date":"2026-11-04","hours":1.5},headers=E); assert r.status_code==201,r.text; oid=r.json()["overtime_id"]
assert [m.to_address for m in mails()[n0:]]==["mgr@gmail.com"]; ok("20 overtime apply -> manager emailed")
n0=len(mails()); assert c.put(f"/api/overtime/{oid}/decision",json={"approve":True},headers=M).status_code==200
assert mails()[-1].to_address=="eve@gmail.com" and "approved" in mails()[-1].subject; ok("21 overtime approve -> employee emailed")
# auto-approved OT (shift without approval) -> no email
d3=SessionLocal(); e3=d3.query(Employee).get(emp_e.employee_id); e3.shift_id=sh2.shift_id; d3.commit(); d3.close()
n0=len(mails()); c.post("/api/overtime",json={"work_date":"2026-11-05","hours":1},headers=E); assert len(mails())==n0; ok("22 auto-approved OT -> no 'awaiting decision' email")

# attendance late alert (late_cutoff 00:00:01 => always late)
n0=len(mails()); r=c.post("/api/attendance/check-in",headers=S); assert r.status_code==201,r.text
new=mails()[n0:]; assert [m.to_address for m in new]==["sam@gmail.com"] and new[0].template=="late_arrival"; ok("23 late check-in -> alert email")
assert c.post("/api/attendance/check-in",headers=S).status_code==409 and len(mails())==n0+1; ok("24 second check-in rejected, no duplicate alert")
# on-time -> none
n0=len(mails()); r=c.post("/api/attendance/check-in",headers=E); assert r.status_code==201 and len(mails())==n0 and r.json()["is_late"] in (0,False); ok("25 on-time check-in -> no alert")

# preferences
assert c.get("/api/email/preferences",headers=M).json()[0]["enabled"] is True
r=c.put("/api/email/preferences",json={"preferences":{"leave_overtime":False}},headers=M); assert r.status_code==200
assert c.put("/api/email/preferences",json={"preferences":{"invitation":False}},headers=M).status_code==422; ok("26 cannot turn off essential categories")
n0=len(mails()); c.post("/api/leave-requests",json=lv,headers=E); assert len(mails())==n0; ok("27 manager opted out -> no email")
nots=c.get("/api/notifications/me",headers=M).json(); assert any("leave" in n["title"].lower() for n in nots); ok("28 in-app notification still written")
c.put("/api/email/preferences",json={"preferences":{"leave_overtime":True}},headers=M)

# forgot password -> personal address
n0=len(mails()); assert c.post("/api/auth/forgot-password",json={"email":emp_u.email}).status_code==200
m=mails()[n0:]; assert [x.to_address for x in m]==["eve@gmail.com"] and m[0].category=="password_reset"
otp=re.search(r"\b(\d{6})\b",m[0].body).group(1); ok("29 forgot password -> OTP to personal email")
n0=len(mails()); assert c.post("/api/auth/forgot-password",json={"email":"nobody@meridian.com"}).status_code==200 and len(mails())==n0; ok("30 unknown email -> same reply, no mail")
n0=len(mails()); r=c.post("/api/auth/reset-password",json={"email":emp_u.email,"otp_code":otp,"new_password":"Reset@12345","confirm_password":"Reset@12345"}); assert r.status_code==200,r.text
assert mails()[-1].template=="security_alert"; ok("31 reset -> security alert email")

# 2FA alerts
import pyotp
E2=login(emp_u.email,"Reset@12345"); c.post("/api/auth/2fa/setup",headers=E2)
sec=SessionLocal().query(User).get(emp_u.user_id).totp_secret; n0=len(mails())
assert c.post("/api/auth/2fa/confirm",json={"code":pyotp.TOTP(sec).now()},headers=E2).status_code==200
assert "enabled" in mails()[-1].subject; ok("32 2FA enabled -> security email")

# change personal email: Manager blocked, HR ok, old address warned
assert c.patch(f"/api/employees/{emp_e.employee_id}/personal-email",json={"personal_email":"new@gmail.com"},headers=M).status_code==403
n0=len(mails()); assert c.patch(f"/api/employees/{emp_e.employee_id}/personal-email",json={"personal_email":"new@gmail.com"},headers=H).status_code==200
assert mails()[n0].to_address=="eve@gmail.com"; ok("33 personal email change: Manager 403, HR ok, OLD address warned")

# failure/retry
run_worker()
orig=email_worker.deliver_email
def boom(*a,**k): raise core_email.EmailDeliveryError("smtp down")
email_worker.deliver_email=boom
c.post("/api/leave-requests",json=lv,headers=E); jid=mails()[-1].email_id
for i in range(4):
    d2=SessionLocal(); jb=d2.query(EmailQueue).get(jid); jb.next_attempt_at=datetime.utcnow()-timedelta(seconds=1); d2.commit(); d2.close(); run_worker()
jb=mails(email_id=jid)[0]; assert jb.status=="Failed" and jb.attempts==4 and "smtp down" in jb.last_error; ok("34 SMTP down -> 4 attempts then Failed with error")
d2=SessionLocal(); jb=d2.query(EmailQueue).get(jid); jb.next_attempt_at=datetime.utcnow()-timedelta(seconds=1); jb.status="Pending"; jb.attempts=1; d2.commit(); d2.close()
run_worker(); jb=mails(email_id=jid)[0]; assert jb.status=="Pending" and jb.attempts==2 and jb.next_attempt_at>datetime.utcnow()+timedelta(minutes=4); ok("35 backoff schedules next retry (5 min)")
email_worker.deliver_email=orig
log=c.get("/api/email/log",params={"status":"Failed"},headers=H).json(); assert all("body" not in x for x in log); 
assert c.get("/api/email/log",headers=E).status_code==403 and c.get("/api/email/log",headers=M).status_code==403; ok("36 Email Log: Admin/HR only, no bodies")
d2=SessionLocal(); jb=d2.query(EmailQueue).get(jid); jb.status="Failed"; d2.commit(); d2.close()
r=c.post(f"/api/email/log/{jid}/retry",headers=H); assert r.status_code==200 and r.json()["status"]=="Pending"
run_worker(); assert mails(email_id=jid)[0].status=="Sent"; ok("37 manual retry -> Sent")
assert c.post(f"/api/email/log/{jid}/retry",headers=H).status_code==400; ok("38 retry only for Failed")

# reminders
run_worker()
d2=SessionLocal()
for lr in d2.query(__import__("app.models.leave",fromlist=["LeaveRequest"]).LeaveRequest).filter_by(status="Pending"): lr.applied_at=datetime.now()-timedelta(days=5)
d2.commit(); d2.close()
n0=len(mails()); res=email_service.run_daily_reminders(SessionLocal()); new=[m for m in mails()[n0:] if m.template=="pending_reminder"]
assert new and len({m.to_address for m in new})==len(new); ok(f"39 reminders: one combined email per approver ({[m.to_address for m in new]})")
n0=len(mails()); email_service.run_daily_reminders(SessionLocal()); assert len(mails())==n0; ok("40 reminders not repeated same day")
# invitation expiring reminder
d2=SessionLocal(); uo=d2.query(User).get(olga.user_id); uo.setup_token_expiry=datetime.utcnow()+timedelta(hours=5); uo.setup_reminded_at=None; d2.commit(); d2.close()
n0=len(mails()); email_service.run_daily_reminders(SessionLocal()); new=[m for m in mails()[n0:] if m.template=="invitation_expiring"]
assert new; ok(f"41 expiring-invitation reminder -> {[m.to_address for m in new]}")
# email failure never breaks request
orig_q=email_service.queue_email
def broken(*a,**k): raise RuntimeError("db exploded")
email_service.queue_email=broken
r=c.post("/api/leave-requests",json=lv,headers=E); assert r.status_code==201; ok("42 email error does NOT break the leave request")
email_service.queue_email=orig_q
print("\nALL TESTS PASSED")
