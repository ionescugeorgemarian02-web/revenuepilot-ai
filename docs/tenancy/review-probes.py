"""Independent reviewer probes for eaa99e0. Assert observed defects, NOT regression acceptance.
Run: python3 -B -I docs/tenancy/review-probes.py
After remediation these assertions should fail; replace with real regression tests.
"""
from pathlib import Path
import sys
import threading
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from revenuepilot.tenancy import TenancyService, AccessDenied, NotFound
from revenuepilot.auth import AuthService


def world():
    t = TenancyService()
    org = t.create_organization('Synthetic', 'admin')
    admin = t.context('admin', org)
    for user, role in [('editor', 'editor'), ('approver', 'approver'), ('viewer', 'viewer')]:
        t.add_member(admin, user, role)
    return t, org, admin


def partial_update():
    t, org, admin = world()
    editor, approver = t.context('editor', org), t.context('approver', org)
    t.create(editor, 'campaign', 'Approved title', 'Original body')
    t.approve(approver, 'r1')
    try:
        t.update(editor, 'r1', title='UNAPPROVED TITLE', body='')
    except ValueError:
        pass
    else:
        raise AssertionError('Expected rejected invalid body')
    item = t.get(approver, 'r1')
    assert (item['title'], item['status'], item['version']) == ('UNAPPROVED TITLE', 'approved', 1)
    print('R11-1 REPRODUCED: rejected edit changed approved content, version still 1')


def missing_deny():
    t, org, admin = world()
    t.create(t.context('editor', org), 'brief', 'Private', 'Secret', visibility='private')
    before = len(t.audit)
    try:
        t.get(t.context('viewer', org), 'r1')
    except NotFound:
        pass
    else:
        raise AssertionError('Private resource unexpectedly visible')
    assert [e.decision for e in t.audit[before:]] == ['allow']
    print('R11-3 REPRODUCED: invisible resource denied, audit records only allow')


def wrong_types():
    t, org, admin = world()
    try:
        t.create(t.context('editor', org), [], 'title', 'body')
    except TypeError:
        print('R11-4 REPRODUCED: JSON-compatible list kind raises uncaught TypeError')
    else:
        raise AssertionError('Expected TypeError in reviewed revision')


def safe_controls():
    t, org, admin = world()
    ed = t.context('editor', org)
    t.create(ed, 'campaign', 'Private', 'secret', visibility='private')
    t.grant_read(ed, 'r1', 'viewer')
    t.add_member(admin, 'editor', 'viewer')
    try:
        t.update(ed, 'r1', title='stale')
    except AccessDenied as e:
        assert e.code == 'stale_membership'
    else:
        raise AssertionError('Old context accepted')
    assert t.export(admin)['items'] == []
    assert t.get(t.context('viewer', org), 'r1')['body'] == 'secret'
    t.remove_member(admin, 'viewer')
    try:
        t.context('viewer', org)
    except AccessDenied:
        pass
    else:
        raise AssertionError('Removed member accepted')
    print('PASS: stale context denied, private export filtered, existing grant persists on owner demotion; receiver removal denies')


def switch_removal_race():
    t = TenancyService()
    a = AuthService(tenancy=t)
    t.user_exists = a.user_exists
    u = a.add_user('race-user', 'Synthetic-Password-123')
    org_a = t.create_organization('A', u.user_id)
    org_b = t.create_organization('B', 'bootstrap')
    admin_b = t.context('bootstrap', org_b)
    t.add_member(admin_b, u.user_id, 'viewer')
    token, _ = a.login('race-user', 'Synthetic-Password-123', 'local', org_a)
    original = t.membership
    removed = False
    def membership(uid, org):
        nonlocal removed
        result = original(uid, org)
        if org == org_b and not removed:
            removed = True
            t.remove_member(admin_b, uid)
        return result
    t.membership = membership
    new_token, principal = a.switch_organization(token, org_b)
    assert principal.tenant_id is None
    try:
        t.context(a.authenticate(new_token).user_id, org_b)
    except AccessDenied:
        print('PASS: removal between switch membership check and rotation grants no tenant access')
    else:
        raise AssertionError('Revoked membership accepted')


def http_wrong_type():
    import http.client
    import json
    from revenuepilot.app import Handler, ThreadingHTTPServer
    t = TenancyService()
    a = AuthService(tenancy=t, cookie_secure=False)
    t.user_exists = a.user_exists
    u = a.add_user('http-user', 'Synthetic-Password-123')
    org = t.create_organization('HTTP fixture', 'bootstrap')
    t.add_member(t.context('bootstrap', org), u.user_id, 'editor')
    token, _ = a.login('http-user', 'Synthetic-Password-123', 'local')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.auth, server.tenancy = a, t
    server.handle_error = lambda *args: None  # expected TypeError already reproduced above
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
    host = f'127.0.0.1:{server.server_port}'
    try:
        conn.request('POST', '/api/resources', json.dumps({'kind': [], 'title': 't', 'body': 'b'}),
                     {'Content-Type': 'application/json', 'Origin': 'http://' + host,
                      'Cookie': a.cookie_name + '=' + token})
        try:
            response = conn.getresponse()
        except http.client.RemoteDisconnected:
            print('R11-4 HTTP REPRODUCED: valid JSON kind=[] closes connection instead of 400')
        else:
            raise AssertionError(f'Expected disconnect in reviewed revision, got {response.status}')
    finally:
        conn.close()
        server.shutdown()
        thread.join(2)
        server.server_close()


def lock_inversion():
    t = TenancyService()
    a = AuthService(tenancy=t)
    t.user_exists = a.user_exists
    u = a.add_user('synthetic-admin', 'Synthetic-Password-123')
    v = a.add_user('synthetic-member', 'Synthetic-Password-456')
    org = t.create_organization('Synthetic', u.user_id)
    ctx = t.context(u.user_id, org)
    login_holds = threading.Event()
    member_holds = threading.Event()
    original_principal, original_exists = a._principal, t.user_exists
    def principal(*args):
        login_holds.set()  # login holds auth._lock here
        assert member_holds.wait(2)
        return original_principal(*args)  # requests tenancy._lock
    def exists(uid):
        member_holds.set()  # add_member holds tenancy._lock here
        assert login_holds.wait(2)
        return original_exists(uid)  # requests auth._lock
    a._principal, t.user_exists = principal, exists
    login = threading.Thread(target=lambda: a.login('synthetic-admin', 'Synthetic-Password-123', 'local'), daemon=True)
    member = threading.Thread(target=lambda: t.add_member(ctx, v.user_id, 'viewer'), daemon=True)
    login.start()
    assert login_holds.wait(2)
    member.start()
    assert member_holds.wait(2)
    login.join(.5)
    member.join(.5)
    assert login.is_alive() and member.is_alive()
    assert a._lock.locked()
    assert not t._lock.acquire(blocking=False)
    print('R11-2 REPRODUCED: both threads remain blocked, auth/tenancy locks held in opposite order')


if __name__ == '__main__':
    partial_update()
    missing_deny()
    wrong_types()
    safe_controls()
    switch_removal_race()
    http_wrong_type()
    lock_inversion()  # isolated daemon threads; process exits without hanging
