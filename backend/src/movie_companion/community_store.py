"""Movie community opinions, deliberately separate from factual evidence/RAG."""
from datetime import datetime, timezone
import hashlib
import json
from .accounts import AccountError


def iso(value):return datetime.fromtimestamp(value,timezone.utc).isoformat()

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()

class CommunityStore:
    def __init__(self,accounts):
        self.accounts=accounts
        with accounts.connect() as db:
            schema='''
                CREATE TABLE IF NOT EXISTS community_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, movie_id INTEGER NOT NULL,
                    author TEXT NOT NULL REFERENCES users(id), title TEXT NOT NULL, body TEXT NOT NULL,
                    spoilers INTEGER NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL DEFAULT 'visible',
                    request_key TEXT NOT NULL, request_hash TEXT NOT NULL, UNIQUE(author,request_key));
                CREATE INDEX IF NOT EXISTS community_movie ON community_threads(movie_id,state,id DESC);
                CREATE TABLE IF NOT EXISTS community_replies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INTEGER NOT NULL REFERENCES community_threads(id),
                    author TEXT NOT NULL REFERENCES users(id), body TEXT NOT NULL, spoilers INTEGER NOT NULL,
                    parent_id INTEGER REFERENCES community_replies(id), depth INTEGER NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    state TEXT NOT NULL DEFAULT 'visible', request_key TEXT NOT NULL,
                    request_hash TEXT NOT NULL, UNIQUE(author,request_key));
                CREATE INDEX IF NOT EXISTS community_reply_thread ON community_replies(thread_id,id);
                CREATE TABLE IF NOT EXISTS community_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, reporter TEXT NOT NULL REFERENCES users(id),
                    kind TEXT NOT NULL, target_id INTEGER NOT NULL, reason TEXT NOT NULL, details TEXT NOT NULL,
                    created REAL NOT NULL, target_revision INTEGER NOT NULL, state TEXT NOT NULL DEFAULT 'open', UNIQUE(reporter,kind,target_id,target_revision));
                CREATE TABLE IF NOT EXISTS community_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT NOT NULL REFERENCES users(id),
                    report_id INTEGER NOT NULL REFERENCES community_reports(id), action TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS community_limits (
                    owner TEXT PRIMARY KEY REFERENCES users(id), began REAL NOT NULL, count INTEGER NOT NULL);
            '''
            for statement in schema.split(';'):
                if statement.strip():db.execute(statement)

    def moderator(self,owner):return owner in self.accounts.moderator_ids

    def limit_write(self,owner):
        now=self.accounts.clock()
        with self.accounts.connect() as db:
            row=db.execute('SELECT * FROM community_limits WHERE owner=?',(owner,)).fetchone()
            limit=120 if self.moderator(owner) else 30
            if row and row['began']+900>now and row['count']>=limit:
                raise AccountError(429,'You have posted several changes recently. Try again shortly.',retry_after=max(1,int(row['began']+900-now)))
            if row and row['began']+900>now:
                db.execute('UPDATE community_limits SET count=count+1 WHERE owner=?',(owner,))
            else:db.execute('INSERT INTO community_limits VALUES (?,?,1) ON CONFLICT(owner) DO UPDATE SET began=excluded.began,count=1',(owner,now))

    def _row(self,db,kind,id):
        table='community_threads' if kind=='thread' else 'community_replies'
        row=db.execute(f'SELECT p.*,u.username FROM {table} p JOIN users u ON u.id=p.author WHERE p.id=?',(id,)).fetchone()
        if row is None:raise AccountError(404,'This discussion is no longer available.')
        return row

    def _thread(self,db,id):
        row=self._row(db,'thread',id)
        if row['state']!='visible':raise AccountError(404,'This discussion is no longer available.')
        return row

    def _spoilers(self,db,row,thread=None):
        if thread is None:return bool(row['spoilers'])
        flagged=bool(thread['spoilers'] or row['spoilers']);parent=row['parent_id'];seen=set()
        while parent:
            if parent in seen:raise AccountError(503,'Reply context could not be verified.')
            seen.add(parent)
            ancestor=db.execute('SELECT parent_id,spoilers,thread_id FROM community_replies WHERE id=?',(parent,)).fetchone()
            if ancestor is None or ancestor['thread_id']!=thread['id'] or len(seen)>3:
                raise AccountError(503,'Reply context could not be verified.')
            flagged=flagged or bool(ancestor['spoilers']);parent=ancestor['parent_id']
        return flagged

    def _view(self,db,row,owner,allowed,thread=None):
        spoilers=self._spoilers(db,row,thread);locked=spoilers and not allowed
        removed=row['state']!='visible';own=row['author']==owner and not removed
        return {'id':row['id'],'title':None if thread is not None or removed else 'Spoiler discussion' if locked else row['title'],
                'body':None if removed or locked else row['body'],
                'author':'Removed post' if removed else row['username'],
                'created_at':iso(row['created']),'updated_at':iso(row['updated']),
                'revision':row['revision'],'spoilers':spoilers,'spoiler_locked':locked,
                'removed':removed,'can_edit':own and not locked,'can_delete':own,
                'parent_id':row['parent_id'] if thread is not None else None,
                'depth':row['depth'] if thread is not None else 0,
                'replies':0 if thread is not None else db.execute('SELECT COUNT(*) FROM community_replies WHERE thread_id=?',(row['id'],)).fetchone()[0]}

    def threads(self,movie_id,owner,page,allowed):
        with self.accounts.connect() as db:
            total=db.execute("SELECT COUNT(*) FROM community_threads WHERE movie_id=? AND state='visible'",(movie_id,)).fetchone()[0]
            rows=db.execute("SELECT p.*,u.username FROM community_threads p JOIN users u ON u.id=p.author WHERE movie_id=? AND state='visible' ORDER BY p.id DESC LIMIT 20 OFFSET ?",(movie_id,(page-1)*20)).fetchall()
            return {'viewer_id':owner,'items':[self._view(db,r,owner,allowed) for r in rows],'page':page,'total':total,'has_more':page*20<total}

    def thread(self,id,owner,allowed):
        with self.accounts.connect() as db:return {'viewer_id':owner,'thread':self._view(db,self._thread(db,id),owner,allowed)}

    def replies(self,id,owner,page,allowed):
        with self.accounts.connect() as db:
            thread=self._thread(db,id)
            total=db.execute('SELECT COUNT(*) FROM community_replies WHERE thread_id=?',(id,)).fetchone()[0]
            rows=db.execute('SELECT p.*,u.username FROM community_replies p JOIN users u ON u.id=p.author WHERE thread_id=? ORDER BY p.id LIMIT 30 OFFSET ?',(id,(page-1)*30)).fetchall()
            return {'viewer_id':owner,'items':[self._view(db,r,owner,allowed,thread) for r in rows],'page':page,'total':total,'has_more':page*30<total}

    def _retry(self,db,kind,owner,key,hashed):
        table='community_threads' if kind=='thread' else 'community_replies'
        row=db.execute(f'SELECT * FROM {table} WHERE author=? AND request_key=?',(owner,str(key))).fetchone()
        if not row:return None
        if row['request_hash']!=hashed:raise AccountError(409,'This submission changed. Start a new post before retrying.')
        if row['state']!='visible':raise AccountError(409,'This post was removed. Start a new post.')
        return {'viewer_id':owner,'id':row['id']}

    def create_thread(self,movie_id,owner,body):
        hashed=digest({'movie_id':movie_id,**body.model_dump(exclude={'request_key'})});now=self.accounts.clock()
        with self.accounts.connect() as db:
            previous=self._retry(db,'thread',owner,body.request_key,hashed)
            if previous:return previous
            cursor=db.execute('INSERT INTO community_threads (movie_id,author,title,body,spoilers,created,updated,request_key,request_hash) VALUES (?,?,?,?,?,?,?,?,?)',
                (movie_id,owner,body.title,body.body,body.spoilers,now,now,str(body.request_key),hashed))
            return {'viewer_id':owner,'id':cursor.lastrowid}

    def create_reply(self,thread_id,owner,body):
        hashed=digest({'thread_id':thread_id,**body.model_dump(exclude={'request_key'})});now=self.accounts.clock()
        with self.accounts.connect() as db:
            thread=self._thread(db,thread_id);depth=0
            previous=self._retry(db,'reply',owner,body.request_key,hashed)
            if previous:return previous
            spoilers=body.spoilers or bool(thread['spoilers'])
            if body.parent_id:
                parent=self._row(db,'reply',body.parent_id)
                if parent['thread_id']!=thread_id or parent['state']!='visible':raise AccountError(422,'Choose a reply in this discussion.')
                depth=parent['depth']+1
                if depth>3:raise AccountError(422,'This reply chain is full. Reply to the discussion instead.')
                spoilers=spoilers or self._spoilers(db,parent,thread)
            cursor=db.execute('INSERT INTO community_replies (thread_id,author,body,spoilers,parent_id,depth,created,updated,request_key,request_hash) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (thread_id,owner,body.body,spoilers,body.parent_id,depth,now,now,str(body.request_key),hashed))
            return {'viewer_id':owner,'id':cursor.lastrowid}

    def edit(self,kind,id,owner,body):
        with self.accounts.connect() as db:
            row=self._row(db,kind,id)
            if row['author']!=owner:raise AccountError(403,'You can only edit your own posts.')
            if kind=='reply':self._thread(db,row['thread_id'])
            if row['state']!='visible':raise AccountError(409,'This post is no longer editable.')
            if row['revision']!=body.revision:raise AccountError(409,'This post changed. Reload before editing.')
            table='community_threads' if kind=='thread' else 'community_replies'
            if kind=='thread':db.execute(f'UPDATE {table} SET title=?,body=?,spoilers=?,revision=revision+1,updated=? WHERE id=?',(body.title,body.body,body.spoilers,self.accounts.clock(),id))
            else:db.execute(f'UPDATE {table} SET body=?,spoilers=?,revision=revision+1,updated=? WHERE id=?',(body.body,body.spoilers,self.accounts.clock(),id))
            return {'viewer_id':owner,'id':id}

    def delete(self,kind,id,owner,revision):
        with self.accounts.connect() as db:
            row=self._row(db,kind,id)
            if row['author']!=owner:raise AccountError(403,'You can only remove your own posts.')
            if row['revision']!=revision:raise AccountError(409,'This post changed. Reload before removing it.')
            table='community_threads' if kind=='thread' else 'community_replies'
            db.execute(f"UPDATE {table} SET body='',state='deleted',revision=revision+1,updated=? WHERE id=?",(self.accounts.clock(),id))
            if kind=='thread':db.execute("UPDATE community_threads SET title='' WHERE id=?",(id,))
            db.execute("UPDATE community_reports SET state='resolved' WHERE kind=? AND target_id=? AND state='open'",(kind,id))
            return {'viewer_id':owner,'id':id}

    def report(self,owner,body):
        with self.accounts.connect() as db:
            row=self._row(db,body.kind,body.target_id)
            if body.kind=='reply':self._thread(db,row['thread_id'])
            if row['state']!='visible':raise AccountError(404,'This post is no longer available.')
            if row['author']==owner:raise AccountError(422,'Use your post controls to edit or remove your own content.')
            previous=db.execute('SELECT id FROM community_reports WHERE reporter=? AND kind=? AND target_id=? AND target_revision=?',(owner,body.kind,body.target_id,row['revision'])).fetchone()
            if previous:return {'viewer_id':owner,'id':previous['id']}
            cur=db.execute('INSERT INTO community_reports (reporter,kind,target_id,reason,details,created,target_revision) VALUES (?,?,?,?,?,?,?)',(owner,body.kind,body.target_id,body.reason,body.details.strip(),self.accounts.clock(),row['revision']))
            return {'viewer_id':owner,'id':cur.lastrowid}

    def reports(self,owner,page,allowed,state='open'):
        if not self.moderator(owner):raise AccountError(403,'Moderator access is required.')
        with self.accounts.connect() as db:
            total=db.execute("SELECT COUNT(*) FROM community_reports WHERE state=?",(state,)).fetchone()[0]
            rows=db.execute("SELECT r.*,u.username FROM community_reports r JOIN users u ON u.id=r.reporter WHERE state=? ORDER BY r.id DESC LIMIT 20 OFFSET ?",(state,(page-1)*20)).fetchall();items=[]
            for row in rows:
                post=self._row(db,row['kind'],row['target_id'])
                thread=None if row['kind']=='thread' else self._row(db,'thread',post['thread_id'])
                spoilers=self._spoilers(db,post,thread);locked=spoilers and not allowed
                items.append({'id':row['id'],'kind':row['kind'],'target_id':row['target_id'],
                    'movie_id':post['movie_id'] if thread is None else thread['movie_id'],
                    'reason':row['reason'],'details':None if not allowed else row['details'],
                    'reporter':row['username'],'created_at':iso(row['created']),'state':row['state'],
                    'content_state':post['state'],'title':None if thread is not None or locked else post['title'],
                    'body':None if locked else post['body'],'spoilers':spoilers,'spoiler_locked':locked,'revision':post['revision']})
            return {'viewer_id':owner,'items':items,'page':page,'total':total,'has_more':page*20<total}

    def moderate(self,owner,id,body):
        if not self.moderator(owner):raise AccountError(403,'Moderator access is required.')
        with self.accounts.connect() as db:
            report=db.execute('SELECT * FROM community_reports WHERE id=?',(id,)).fetchone()
            if report is None or report['state']!='open' and body.action!='restore':raise AccountError(409,'This report was already reviewed. Reload the queue.')
            post=self._row(db,report['kind'],report['target_id'])
            if post['revision']!=body.revision:raise AccountError(409,'This post changed. Reload the report before acting.')
            if body.action!='dismiss':
                if post['state']=='deleted':raise AccountError(409,'Removed posts cannot be restored.')
                if body.action=='restore' and post['state']!='hidden':raise AccountError(409,'Only moderator-hidden posts can be restored.')
                table='community_threads' if report['kind']=='thread' else 'community_replies'
                state='hidden' if body.action=='hide' else 'visible'
                db.execute(f'UPDATE {table} SET state=?,revision=revision+1,updated=? WHERE id=?',(state,self.accounts.clock(),post['id']))
            db.execute("UPDATE community_reports SET state='resolved' WHERE kind=? AND target_id=? AND state='open'",(report['kind'],report['target_id']))
            db.execute('INSERT INTO community_audit (actor,report_id,action,created) VALUES (?,?,?,?)',(owner,id,body.action,self.accounts.clock()))
            return {'viewer_id':owner,'id':id}
