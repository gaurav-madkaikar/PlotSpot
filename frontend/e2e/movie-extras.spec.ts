import {expect,test} from './fixtures'

const checked_at='2026-10-11T00:00:00Z'
const watch=(country:string,stale=false)=>({movie_id:27205,country,status:'available',groups:[{kind:'subscription',providers:[{id:8,name:`${country} Stream`,logo_url:'https://image.tmdb.org/t/p/w92/logo.jpg'}]},{kind:'rent',providers:[{id:9,name:`${country} Rental`,logo_url:null}]}],watch_url:`https://www.themoviedb.org/movie/27205-inception/watch?locale=${country}`,checked_at,stale})

test('country-specific availability, attribution and stale notice work without mobile overflow',async({page})=>{
  await page.setViewportSize({width:375,height:812})
  await page.route('https://image.tmdb.org/t/p/w92/**',route=>route.abort())
  await page.route('**/api/movies/27205/watch?*',route=>{
    const country=new URL(route.request().url()).searchParams.get('country')!
    return route.fulfill({json:watch(country,country==='US')})
  })
  await page.goto('/movies/27205#watch')
  await expect(page.getByRole('heading',{name:'Where to watch',exact:true})).toBeVisible()
  await expect(page.getByText('IN Stream',{exact:true})).toBeVisible()
  await expect(page.getByText('Subscription',{exact:true})).toBeVisible()
  await expect(page.getByText('Rent',{exact:true})).toBeVisible()
  await expect(page.getByRole('link',{name:'JustWatch',exact:true})).toHaveAttribute('href','https://www.justwatch.com/')
  await expect(page.getByRole('link',{name:'View watch options'})).toHaveAttribute('href',watch('IN').watch_url)
  await page.getByLabel('Country',{exact:true}).selectOption('US')
  await expect(page.getByText('US Stream',{exact:true})).toBeVisible()
  await expect(page.getByText('IN Stream',{exact:true})).toHaveCount(0)
  await expect(page.getByText('Showing previously checked options. Availability could not be refreshed.')).toBeVisible()
  await expect(page.getByRole('link',{name:'View watch options'})).toHaveAttribute('href',watch('US').watch_url)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.reload()
  await expect(page.getByLabel('Country',{exact:true})).toHaveValue('US')
})

test('a slower previous country cannot overwrite the selected country',async({page})=>{
  let release:()=>void=()=>{}
  const gate=new Promise<void>(resolve=>{release=resolve})
  let started=false
  await page.route('**/api/movies/27205/watch?*',async route=>{
    const country=new URL(route.request().url()).searchParams.get('country')!
    if(country==='IN'){started=true;await gate}
    await route.fulfill({json:watch(country)}).catch(()=>{})
  })
  await page.goto('/movies/27205#watch')
  await expect.poll(()=>started).toBe(true)
  await page.getByLabel('Country',{exact:true}).selectOption('US')
  await expect(page.getByText('US Stream',{exact:true})).toBeVisible()
  release()
  await expect(page.getByText('IN Stream',{exact:true})).toHaveCount(0)
  await expect(page.getByLabel('Country',{exact:true})).toHaveValue('US')
})

test('optional failures recover independently and empty availability stays honest',async({page})=>{
  await page.route('**/api/movies/27205/watch?*',route=>route.fulfill({status:503,json:{}}))
  await page.goto('/movies/27205#watch')
  await expect(page.getByText('Watch options are unavailable right now.')).toBeVisible()
  await expect(page.getByRole('heading',{name:'Inception',exact:true})).toBeVisible()
  await page.unroute('**/api/movies/27205/watch?*')
  await page.getByRole('button',{name:'Retry watch options'}).click()
  await expect(page.getByText('No watch options are listed for India.')).toBeVisible()
  await page.route('**/api/movies/27205/related',route=>route.fulfill({status:503,json:{}}))
  await page.goto('/movies/27205#related')
  await expect(page.getByText('Related films are unavailable right now.')).toBeVisible()
  await page.unroute('**/api/movies/27205/related')
  await page.getByRole('button',{name:'Retry related films'}).click()
  await expect(page.getByText('No related films are listed yet.')).toBeVisible()
})

test('related tiles include adult records, fetch full details only on selection and return to the source film',async({page})=>{
  await page.setViewportSize({width:375,height:812})
  await page.route('https://image.tmdb.org/t/p/w500/**',route=>route.abort())
  await page.route('**/api/movies/27205/related',route=>route.fulfill({json:{movie_id:27205,checked_at,stale:false,items:Array.from({length:6},(_,i)=>({id:999+i,title:`Related film ${i+1}`,year:2000+i,adult:i===0,poster_url:'https://image.tmdb.org/t/p/w500/fixture.jpg'}))}}))
  let reads=0
  await page.route('**/api/movies/999',route=>{
    reads++
    return route.fulfill({json:{id:999,title:'Related film 1',year:2000,runtime_minutes:100,language:'English',genres:[],director:null,cast:[],overview:'Related film synopsis.',tagline:'',cover_url:null,source:'tmdb',artwork_kind:'placeholder'}})
  })
  await page.goto('/movies/27205#related')
  await expect(page.locator('.related-tile')).toHaveCount(6)
  expect(reads).toBe(0)
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await page.getByRole('link',{name:'Explore Related film 1',exact:true}).click()
  await expect(page).toHaveURL(/\/movies\/999$/)
  await expect(page.getByRole('heading',{name:'Related film 1',exact:true,level:1})).toBeVisible()
  await expect.poll(()=>reads).toBe(1)
  await page.goBack()
  await expect(page).toHaveURL(/\/movies\/27205#related$/)
  await expect(page.getByRole('heading',{name:'More like this',exact:true})).toBeVisible()
})
