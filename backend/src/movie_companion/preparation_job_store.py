"""Local SQLite draft queue with expiring ownership and fenced checkpoint writes."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time

ACTIVE={'queued','running'}
MAX_ATTEMPTS=3


class LeaseLost(RuntimeError):
    pass


class PreparationJobStore:
    def __init__(self,path,*,validate,clock=time.time,lease_seconds=30):
        self.path=Path(path);self.validate=validate;self.clock=clock;self.lease_seconds=lease_seconds
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (movie_id INTEGER PRIMARY KEY, id TEXT UNIQUE NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL, sequence INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, owner TEXT, expires REAL, cancel_requested INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS worker (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, expires REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)')

    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=5)
        db.row_factory=sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:db.close()

    def encode(self,record):
        self.validate(record)
        body=json.dumps(record,ensure_ascii=False)
        if len(body.encode())>1_000_000:raise ValueError('Checkpoint exceeds budget')
        return body

    def decode(self,row):
        if row is None:return None
        if len(row['payload'].encode())>1_000_000:raise ValueError('Checkpoint exceeds budget')
        record=json.loads(row['payload']);self.validate(record)
        if record['movie_id']!=row['movie_id'] or record['id']!=row['id'] or record['state']!=row['state']:
            raise ValueError('Checkpoint row identity mismatch')
        return record

    def latest(self,movie_id):
        with self.connection() as db:return self.decode(db.execute('SELECT * FROM jobs WHERE movie_id=?',(movie_id,)).fetchone())

    def enqueue(self,record):
        if record['state']!='queued':raise ValueError('New jobs must be queued')
        body=self.encode(record)
        with self.connection() as db:
            row=db.execute('SELECT * FROM jobs WHERE movie_id=?',(record['movie_id'],)).fetchone()
            if row and row['state'] in ACTIVE:return self.decode(row)
            sequence=db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM jobs').fetchone()[0]
            db.execute('INSERT INTO jobs (movie_id,id,state,payload,sequence) VALUES (?,?,?,?,?) ON CONFLICT(movie_id) DO UPDATE SET id=excluded.id,state=excluded.state,payload=excluded.payload,sequence=excluded.sequence,attempts=0,owner=NULL,expires=NULL,cancel_requested=0',
                       (record['movie_id'],record['id'],'queued',body,sequence))
        return record

    def requeue(self,movie_id,*,report=None):
        """Explicitly retry a terminal job without discarding its checkpoint."""
        with self.connection() as db:
            row=db.execute('SELECT * FROM jobs WHERE movie_id=?',(movie_id,)).fetchone()
            if row is None:raise ValueError('No preparation job exists')
            record=self.decode(row)
            if row['state'] not in ('failed','incomplete','interrupted','needs_review'):
                raise ValueError('Only a failed or incomplete job can be retried')
            if report is not None:record['report']=json.loads(json.dumps(report))
            if not isinstance(record.get('report'),dict) or record['report'].get('state')!='running':
                raise ValueError('Retry requires a resumable running checkpoint')
            if row['state']=='needs_review':
                import hashlib
                previous=json.loads(row['payload']).get('report')
                expected=hashlib.sha256(json.dumps(previous,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if record['report'].get('refinement_of')!=expected:
                    raise ValueError('Review refinement does not identify the completed checkpoint')
            record.update(state='queued',phase=record['report'].get('phase','retrieving'),
                          message='Preparation will continue from its validated checkpoint.')
            sequence=db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM jobs').fetchone()[0]
            db.execute('UPDATE jobs SET state=?,payload=?,sequence=?,attempts=0,owner=NULL,expires=NULL,cancel_requested=0 WHERE movie_id=?',
                       ('queued',self.encode(record),sequence,movie_id))
        return record

    def replace_review(self,movie_id,*,report):
        """Atomically save a refined report that still satisfies its targets."""
        import hashlib
        with self.connection() as db:
            row=db.execute('SELECT * FROM jobs WHERE movie_id=?',(movie_id,)).fetchone()
            if row is None or row['state']!='needs_review':
                raise ValueError('Only a completed review can be replaced')
            record=self.decode(row)
            previous=record.get('report')
            expected=hashlib.sha256(json.dumps(previous,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if (not isinstance(report,dict) or report.get('state')!='needs_review'
                    or report.get('phase')!='finished' or report.get('refinement_of')!=expected):
                raise ValueError('Review replacement does not identify the completed checkpoint')
            record['report']=json.loads(json.dumps(report))
            record.update(state='needs_review',phase='finished',
                          message='Review rejections were applied; remaining drafts still meet the targets.')
            db.execute('UPDATE jobs SET payload=?,attempts=0,owner=NULL,expires=NULL,cancel_requested=0 WHERE movie_id=?',
                       (self.encode(record),movie_id))
        return record

    def leader(self,owner):
        now=self.clock()
        with self.connection() as db:
            row=db.execute('SELECT * FROM worker WHERE id=1').fetchone()
            if row and row['owner']!=owner and row['expires']>now:return False
            db.execute('INSERT INTO worker VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,expires=excluded.expires',(owner,now+self.lease_seconds))
            return True

    def _owns(self,db,owner):
        return db.execute('SELECT 1 FROM worker WHERE id=1 AND owner=? AND expires>?',(owner,self.clock())).fetchone() is not None

    def recover(self,owner):
        with self.connection() as db:
            if not self._owns(db,owner):raise LeaseLost('Worker lease lost')
            rows=db.execute("SELECT * FROM jobs WHERE state='running' AND expires<=?",(self.clock(),)).fetchall()
            for row in rows:
                record=self.decode(row)
                if row['cancel_requested']:
                    record.update(state='cancelled',phase='finished',message='Preparation cancelled. Completed drafts are preserved.')
                elif row['attempts']>=MAX_ATTEMPTS:
                    record.update(state='interrupted',phase='finished',message='Preparation stopped after repeated interruptions. Completed drafts are preserved.')
                else:
                    record.update(state='queued',message='Preparation will resume from its saved checkpoint.')
                db.execute('UPDATE jobs SET state=?,payload=?,owner=NULL,expires=NULL WHERE movie_id=?',(record['state'],self.encode(record),row['movie_id']))

    def pending(self):
        with self.connection() as db:return db.execute("SELECT 1 FROM jobs WHERE state='queued' LIMIT 1").fetchone() is not None

    def claim(self,owner):
        with self.connection() as db:
            if not self._owns(db,owner):raise LeaseLost('Worker lease lost')
            if db.execute("SELECT 1 FROM jobs WHERE state='running' LIMIT 1").fetchone():return None
            row=db.execute("SELECT * FROM jobs WHERE state='queued' ORDER BY sequence LIMIT 1").fetchone()
            if row is None:return None
            record=self.decode(row)
            if row['attempts']>=MAX_ATTEMPTS:
                record.update(state='interrupted',phase='finished',message='Preparation reached its recovery limit. Completed drafts are preserved.')
                db.execute('UPDATE jobs SET state=?,payload=? WHERE movie_id=?',(record['state'],self.encode(record),row['movie_id']))
                return None
            record.update(state='running',message='Resuming movie preparation.' if record.get('report') else 'Loading movie evidence.')
            db.execute('UPDATE jobs SET state=?,payload=?,attempts=attempts+1,owner=?,expires=? WHERE movie_id=?',
                       ('running',self.encode(record),owner,self.clock()+self.lease_seconds,row['movie_id']))
            return record

    def heartbeat(self,owner):
        now=self.clock()
        with self.connection() as db:
            if not self._owns(db,owner):return False
            if db.execute("SELECT 1 FROM jobs WHERE owner=? AND state='running' AND expires<=?",(owner,now)).fetchone():
                return False
            db.execute('UPDATE worker SET expires=? WHERE owner=?',(now+self.lease_seconds,owner))
            db.execute("UPDATE jobs SET expires=? WHERE owner=? AND state='running' AND expires>?",(now+self.lease_seconds,owner,now))
            return True

    def requested_cancel(self,movie_id,job_id):
        with self.connection() as db:
            row=db.execute('SELECT cancel_requested FROM jobs WHERE movie_id=? AND id=?',(movie_id,job_id)).fetchone()
            return bool(row and row[0])

    def save(self,record,owner):
        body=self.encode(record)
        with self.connection() as db:
            row=db.execute("SELECT * FROM jobs WHERE movie_id=? AND id=? AND state='running' AND owner=? AND expires>?",(record['movie_id'],record['id'],owner,self.clock())).fetchone()
            if row is None or not self._owns(db,owner):raise LeaseLost('Checkpoint owner expired or changed')
            if row['cancel_requested'] and record['state']!='cancelled':raise LeaseLost('Cancellation takes precedence')
            db.execute('UPDATE jobs SET state=?,payload=?,owner=?,expires=? WHERE movie_id=?',
                (record['state'],body,owner if record['state']=='running' else None,
                 self.clock()+self.lease_seconds if record['state']=='running' else None,record['movie_id']))

    def cancel(self,movie_id,job_id):
        with self.connection() as db:
            row=db.execute('SELECT * FROM jobs WHERE movie_id=? AND id=?',(movie_id,job_id)).fetchone()
            if row is None or row['state'] not in ACTIVE:raise ValueError('Job is no longer active')
            record=self.decode(row)
            if row['state']=='queued':record.update(state='cancelled',phase='finished',message='Preparation cancelled. Completed drafts are preserved.')
            else:record['message']='Cancellation requested.'
            db.execute('UPDATE jobs SET state=?,payload=?,cancel_requested=1 WHERE movie_id=?',(record['state'],self.encode(record),movie_id))
            return record

    def release(self,owner):
        with self.connection() as db:db.execute('DELETE FROM worker WHERE owner=?',(owner,))

    def migrate(self,root):
        # Original files are retained. An invalid file creates no runnable job.
        with self.connection() as db:
            if db.execute("SELECT 1 FROM migrations WHERE name='legacy-json-v1'").fetchone():return
            for path in sorted(Path(root).glob('*.json')):
                try:
                    if path.stat().st_size>1_000_000:continue
                    record=json.loads(path.read_text());self.validate(record)
                    if path.stem!=str(record['movie_id']):continue
                    if record['state']=='running':record.update(state='interrupted',phase='finished',message='Legacy preparation was interrupted. Start again to use resumable checkpoints.')
                    body=self.encode(record)
                    sequence=db.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM jobs').fetchone()[0]
                    db.execute('INSERT OR IGNORE INTO jobs (movie_id,id,state,payload,sequence) VALUES (?,?,?,?,?)',(record['movie_id'],record['id'],record['state'],body,sequence))
                except (ValueError,TypeError,KeyError,OSError):continue
            db.execute("INSERT INTO migrations VALUES ('legacy-json-v1')")

    def mark_published(self,movie_id,job_id,report_sha256,receipt):
        """Reconcile an already committed content receipt with the terminal job."""
        import hashlib
        with self.connection() as db:
            row=db.execute('SELECT * FROM jobs WHERE movie_id=? AND id=?',(movie_id,job_id)).fetchone()
            if row is None:return False  # a later refresh replaced this job
            record=self.decode(row)
            if record['state']=='published':
                if record['report'].get('publication_receipt',{}).get('selection_sha256')!=receipt['selection_sha256']:
                    raise ValueError('Job publication receipt conflicts')
                return True
            if record['state'] not in ('needs_review','incomplete'):raise ValueError('Job is not reviewable')
            current=hashlib.sha256(json.dumps(record['report'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if current!=report_sha256:raise ValueError('Job changed since review')
            record['report']['publication_approved']=True
            record['report']['publication_receipt']=receipt
            record.update(state='published',phase='finished',message='The reviewed selection was saved to the shared collection.')
            db.execute('UPDATE jobs SET state=?,payload=? WHERE movie_id=? AND id=?',
                       ('published',self.encode(record),movie_id,job_id))
        return True
