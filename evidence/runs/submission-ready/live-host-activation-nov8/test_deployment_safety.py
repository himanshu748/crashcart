"""Offline checks of the exact activation guards; never import/run deployment."""
import ast
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

SOURCE=Path(__file__).with_name('remote_activate.py')
tree=ast.parse(SOURCE.read_text())
functions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'restore_original','without_new_host'}],type_ignores=[])
CODE=compile(functions,str(SOURCE),'exec')

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'Caddyfile';self.path.write_bytes(b'candidate')
        info=self.path.stat();self.away=self.path.with_suffix('.original-inode')
        self.g={'CONFIG':self.path,'old':b'original','candidate':b'candidate','candidate_at_path':None,
            'config_inode':(info.st_dev,info.st_ino),'os':os,'fcntl':fcntl,'stat':stat,'json':json,
            'INSIDE':'/etc/caddy/Caddyfile','HOST':'workspace.test','old_active':{'old':1},
            'active_config':lambda:{'old':1},'container_config':self.path.read_bytes,'run':lambda *a,**kw:b''}
        exec(CODE,self.g)

    def test_restore_same_inode(self):
        self.g['restore_original']();self.assertEqual(self.path.read_bytes(),b'original')
        i=self.path.stat();self.assertEqual((i.st_dev,i.st_ino),self.g['config_inode'])

    def test_refuse_changed_bytes(self):
        self.path.write_bytes(b'other-editor')
        with self.assertRaises(AssertionError):self.g['restore_original']()
        self.assertEqual(self.path.read_bytes(),b'other-editor')

    def test_refuse_other_active_config(self):
        self.g['active_config']=lambda:{'other-editor':1}
        with self.assertRaises(AssertionError):self.g['restore_original']()
        self.assertEqual(self.path.read_bytes(),b'candidate')

    def test_refuse_path_swap_during_validation(self):
        def run(*a,**kw):
            self.path.rename(self.away);self.path.write_bytes(b'other-editor');return b''
        self.g['run']=run
        with self.assertRaises(AssertionError):self.g['restore_original']()
        self.assertEqual(self.path.read_bytes(),b'other-editor');self.assertEqual(self.away.read_bytes(),b'candidate')

    def test_restore_only_old_handle_after_write_swap(self):
        original=os.fsync;calls=[]
        def fsync(fd):
            original(fd);calls.append(fd)
            if len(calls)==1:self.path.rename(self.away);self.path.write_bytes(b'other-editor')
        with patch('os.fsync',fsync):
            with self.assertRaises(RuntimeError):self.g['restore_original']()
        self.assertEqual(self.path.read_bytes(),b'other-editor');self.assertEqual(self.away.read_bytes(),b'candidate')

    def test_remove_only_exact_new_host(self):
        old={'apps':{'http':{'servers':{'srv0':{'routes':[{'match':[{'host':['old.test']}],'handle':[{'x':1}]}]}}}}}
        new=json.loads(json.dumps(old));new['apps']['http']['servers']['srv0']['routes'].insert(0,{'match':[{'host':['workspace.test']}],'handle':[{'x':2}]})
        self.assertEqual(self.g['without_new_host'](new),old)
        self.assertEqual(len(new['apps']['http']['servers']['srv0']['routes']),2)

    def test_reject_shared_host_match(self):
        with self.assertRaises(AssertionError):self.g['without_new_host']({'routes':[{'match':[{'host':['workspace.test','old.test']}]}]})

if __name__=='__main__':unittest.main(verbosity=2)
