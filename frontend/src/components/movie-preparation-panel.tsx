import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelPreparation, getPreparation, startPreparation } from '../lib/api'
import { Button } from './ui/button'

const stages = ['Evidence', 'Retrieval', 'Drafting', 'Review']
const stageIndex = { source:0, retrieving:1, generating:2, reviewing:3, finished:4 }
const stateLabels = {queued:'Queued',running:'Preparing',needs_review:'Ready for review',incomplete:'Partial drafts',failed:'Could not finish',cancelled:'Cancelled',interrupted:'Interrupted',ready:'Saved collection ready',published:'Published'}

export function MoviePreparationPanel({movieId,allowSpoilers}:{movieId:number;allowSpoilers:boolean}) {
  const [open,setOpen] = useState(false)
  const cache = useQueryClient()
  const status = useQuery({
    queryKey:['preparation',movieId],queryFn:({signal})=>getPreparation(movieId,signal),
    enabled:open && allowSpoilers,retry:1,
    refetchInterval:query=>open && allowSpoilers && ['queued','running'].includes(query.state.data?.job?.state ?? '') ? 2000 : false,
  })
  const action = useMutation({
    mutationFn:(jobId:string|null)=>jobId ? cancelPreparation(movieId,jobId) : startPreparation(movieId),
    onSuccess:async data=>{
      await cache.cancelQueries({queryKey:['preparation',movieId]})
      cache.setQueryData(['preparation',movieId],data)
    },
  })
  const job = status.data?.job
  const active = job?.state==='running' || job?.state==='queued'
  return <section className="preparation-panel" aria-labelledby="preparation-heading">
    <button className="preparation-toggle" aria-expanded={open} aria-controls="preparation-body" onClick={()=>setOpen(!open)}>
      <span><span className="eyebrow">CONTENT STUDIO</span><span id="preparation-heading">Draft workspace</span></span>
      <span className="preparation-toggle-label">{open ? 'Close' : 'Explore'}</span>
    </button>
    {open && <div id="preparation-body" className="preparation-body">
      <p className="preparation-intro">Prepare new facts and story questions. Inspect the evidence and review decisions before publication.</p>
      {!allowSpoilers ? <p role="status">Allow spoilers above to open movie drafts.</p> : <>
        {status.isPending && <p role="status">Loading draft status…</p>}
        {status.isError && <div><p role="alert">{status.error.message}</p><Button variant="outline" onClick={()=>void status.refetch()}>Retry draft status</Button></div>}
        {status.data?.available === false && <p>Draft preparation is not available for this film yet.</p>}
        {status.data?.available && <>
          <div className="preparation-toolbar">
            <div><strong>{job ? stateLabels[job.state] : 'Start with the evidence'}</strong><p>{job?.message || 'Preparation may take several minutes. You can leave this page and return.'}</p></div>
            <Button variant="outline" disabled={action.isPending} onClick={()=>action.mutate(active && job ? job.id : null)}>
              {action.isPending ? 'Please wait…' : active ? 'Cancel preparation' : job ? 'Prepare again' : 'Prepare drafts'}
            </Button>
          </div>
          {action.isError && <p role="alert" className="question-error">{action.error.message}</p>}
          {job && <>
            <div role="status" aria-live="polite" className="preparation-counts"><span><strong>{job.facts_retained}</strong> / 5 fact drafts</span><span><strong>{job.questions_retained}</strong> / 10 question drafts</span><span>{job.batches_completed} {job.batches_completed===1 ? 'batch' : 'batches'} reviewed</span></div>
            {active && <ol className="preparation-stages" aria-label="Preparation steps">{stages.map((stage,index)=><li key={stage} aria-current={index===stageIndex[job.phase] ? 'step' : undefined} className={index<stageIndex[job.phase] ? 'complete' : ''}><span>{index+1}</span>{stage}</li>)}</ol>}
            {!!job.items.length && <div className="draft-list">{job.items.map(item=><article className="draft-card" key={item.id}>
              <div className="draft-card-meta"><span>{item.kind==='fact' ? 'Background fact' : 'Story question'}</span><span className={`draft-decision ${item.retained ? 'retained' : 'withheld'}`}>{item.retained ? 'Retained draft' : item.decision==='uncertain' ? 'Needs context' : 'Not retained'}</span></div>
              <h3>{item.title}</h3>{item.text && <p>{item.text}</p>}
              {!!item.options.length && <ol className="draft-options">{item.options.map((option,index)=><li key={index}><span>{String.fromCharCode(65+index)}</span>{option}{index===item.correct_index && <small>Proposed answer</small>}</li>)}</ol>}
              <details className="draft-review"><summary>Review & evidence</summary><p>{item.reason}</p><p className="source-publisher">Wikipedia · {item.origin.section_title}</p><blockquote>{item.evidence_quote}</blockquote><a className="text-link" href={item.origin.source_ref} target="_blank" rel="noopener noreferrer">Read source</a></details>
            </article>)}</div>}
            <p className="preparation-note">Drafts are separate from the saved collection. Review decisions can be wrong.</p>
          </>}
        </>}
      </>}
    </div>}
  </section>
}
