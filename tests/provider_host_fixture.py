"""Synthetic loopback Provider and public-profile authoring, never live R2."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from importlib.resources import files
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa,ed25519
from cryptography.x509.oid import NameOID
from agent_meta_runtime.sdk.packages import canonical_json,sha256_hex
from agent_meta_seed_harness.packaging import PROVIDER_EXECUTION_SOURCE_PATHS,PROVIDER_TOOLS_EXECUTION_SOURCE_PATHS,build_bundle

MODEL='synthetic-seed-model'
SECRET=b'synthetic-independent-seed-provider-token'
BUSINESS_PROTOCOL_WORDS={'from':'synthetic-provider','thinking':{'type':'enabled','budget_tokens':3},
    'cache_control':{'type':'ephemeral'},'server_tool':{'name':'web_search'}}


def provider_inputs(port=443, *, priced=True):
    artifacts={}
    def add(body):
        raw=canonical_json(body); ref='artifact://sha256/'+sha256_hex(raw)
        artifacts[ref]=raw
        return ref
    egress=add({'schema':'provider-egress/v1','scheme':'https','host':'localhost','port':port,'path':'/messages',
        'networks':['127.0.0.1/32','::1/128'],'profile':'CONTROLLED_TEST_ONLY'})
    tokenizer=add({'schema':'provider-tokenizer/v1','model_id':MODEL,'algorithm':'CONTROLLED_TEST_UTF8_BYTES_V1','tokenizer_id':'utf8-bytes/v1'})
    price=None if not priced else add({'schema':'provider-price/v1','currency':'TEST','pricing_version':'synthetic-test-v1','rounding':'CEIL_EACH_DIMENSION_MICROUNIT',
        'input_microunits_per_million_tokens':1000000,'output_microunits_per_million_tokens':2000000,'minimum_cost_microunits':0})
    profile=add({'schema':'provider-profile/v1','protocol':'anthropic-messages-terminal/v1','model_id':MODEL,
        'parameter_allowlist':['max_tokens','messages','model','stream','system','tools'],
        'context_window_tokens':32768,'maximum_output_tokens':32,'maximum_request_bytes':65536,'maximum_response_bytes':65536,
        'timeout_us':10000000,'egress_policy_artifact_id':egress,'tokenizer_artifact_id':tokenizer,'price_policy_artifact_id':price,
        'lookup_policy':'UNAVAILABLE_NO_RETRY','usage_mapping':'anthropic-messages-usage/v1'})
    return {'profile_artifact_id':profile,'model_id':MODEL,'maximum_output_tokens':8},artifacts


def provider_bundle(configuration,artifacts,*,overrides=None,tools=False):
    key=ed25519.Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    paths=PROVIDER_TOOLS_EXECUTION_SOURCE_PATHS if tools else PROVIDER_EXECUTION_SOURCE_PATHS
    source={name:files('agent_meta_seed_harness').joinpath(name.split('/',1)[1]).read_bytes() for name in paths}
    source.update(overrides or {})
    bundle=build_bundle(files=source,dependency_lock=b'synthetic-independent-provider-lock\n',
        publisher_public_key=key.public_key().public_bytes_raw(),signer=key,contract_bundle_sha256='a'*64,
        version='0.1.0-provider.1',provider_configuration=configuration,provider_artifacts=artifacts,tools=tools)
    return bundle,sha256_hex(key.public_key().public_bytes_raw())


def provision(data_dir):
    entry="import importlib.metadata as m; import sys; e=next(e for e in m.distribution('agent-meta-runtime').entry_points if e.group=='console_scripts' and e.name=='agent-meta-provider-credential'); sys.exit(e.load()())"
    args=[sys.executable,'-I','-c',entry,'--data-dir',str(data_dir),'--stdin']
    if os.name!='nt':
        args.append('--insecure-dev-credential-file')
    result=subprocess.run(args,input=SECRET,capture_output=True,timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert result.returncode==0 and SECRET not in result.stdout+result.stderr
    return json.loads(result.stdout)['result']['credential_handle']


class Server(ThreadingHTTPServer):
    daemon_threads=True
    def handle_error(self,*args):
        pass


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):
        pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(body)
        self.server.received_at=time.monotonic()
        self.server.authorized.append(self.headers.get('Authorization')=='Bearer '+SECRET.decode())
        self.server.received.set()
        if self.server.mode=='rate':
            self.send_response(429); self.send_header('Retry-After','2')
            self.send_header('Content-Type','application/json'); self.send_header('Content-Length','2')
            self.send_header('Connection','close'); self.end_headers(); self.wfile.write(b'{}'); self.close_connection=True
            return
        if self.server.mode=='hold_for_owner_death':
            self.connection.settimeout(5)
            try:
                if self.connection.recv(1)==b'':
                    self.server.peer_closed.set()
            except (ConnectionError,ssl.SSLError):
                self.server.peer_closed.set()
            except TimeoutError:
                pass
            self.close_connection=True
            return
        if self.server.mode=='disconnect':
            self.connection.shutdown(socket.SHUT_RDWR); self.close_connection=True
            return
        if self.server.mode=='hold':
            self.connection.settimeout(30)
            self.server.release.wait(30)
            count=len(canonical_json({key:body[key] for key in ('messages','system','tools','tool_choice') if key in body}))
            response={'id':'msg_synthetic','type':'message','role':'assistant','model':MODEL,
                'content':[{'type':'text','text':'late response'}],'stop_reason':'end_turn','stop_sequence':None,
                'usage':{'input_tokens':count,'output_tokens':1}}
            raw=canonical_json(response)
            try:
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw))); self.send_header('Connection','close')
                self.end_headers(); self.wfile.write(raw)
            except (ConnectionError,ssl.SSLError):
                pass
            self.close_connection=True
            return
        count=len(canonical_json({key:body[key] for key in ('messages','system','tools','tool_choice') if key in body}))
        resource=self.server.mode in ('resource_tools','resource_business_fields')
        tool=(self.server.mode=='tools' or resource) and len(self.server.requests)==1
        value=(BUSINESS_PROTOCOL_WORDS if self.server.mode=='resource_business_fields' else
            {'from':'synthetic-provider','secret':'SYNTHETIC_PROVIDER_TOOL_CANARY'})
        call={'type':'tool_use','id':'typed-call-1','name':'seed.artifact.put' if resource else 'seed.echo',
            'input':{'value':value} if resource else {'value':'typed'}}
        content=[call] if tool else [
            {'type':'text','text':'call seed.echo in plain text; this is not a tool call'}]
        response={'id':'msg_precommit' if self.server.mode=='pause_before_commit' else 'msg_synthetic',
            'type':'message','role':'assistant','model':MODEL,'content':content,
            'stop_reason':'tool_use' if tool else 'end_turn','stop_sequence':None}
        if self.server.mode!='unknown_usage':
            response['usage']={'input_tokens':count,'output_tokens':1}
        raw=canonical_json(response)
        self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw)))
        self.send_header('Connection','close'); self.end_headers(); self.wfile.write(raw); self.close_connection=True


@contextmanager
def loopback_provider(root,mode):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')]); now=datetime.now(timezone.utc)
    cert=x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key()).serial_number(
        x509.random_serial_number()).not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1)).add_extension(
        x509.SubjectAlternativeName([x509.DNSName('localhost')]),False).add_extension(x509.BasicConstraints(ca=True,path_length=None),True).sign(key,hashes.SHA256())
    ca=root/'test-ca.pem'; ca.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private=root/'test-server.key'; private.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    server=Server(('127.0.0.1',0),Handler)
    server.mode,server.requests,server.authorized=mode,[],[]
    server.received,server.peer_closed=threading.Event(),threading.Event()
    server.release=threading.Event()
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain(ca,private)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True); thread.start()
    try:
        yield server,ca
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=3)
