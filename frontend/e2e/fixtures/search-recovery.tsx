import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { MovieSearch } from '../../src/components/movie-search'
import { RouteErrorPage } from '../../src/components/route-error-page'
import { AuthProvider } from '../../src/lib/auth'
import { CollectionProvider } from '../../src/lib/collection'
import '../../src/styles.css'

// Deliberately bypass the HTTP parser: this is a pre-update React Query cache.
const client = new QueryClient()
client.setQueryData(
  ['keyword-movies', 'unified=true&page=1&page_size=20&sort_by=trusted'],
  {
    items: [
      {
        id: 329865,
        title: 'Arrival',
        year: 2016,
        genres: ['Science Fiction'],
        cast: ['Amy Adams'],
        cover_url: '/covers/329865.svg',
        artwork_kind: 'illustration',
        source: 'demo',
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    data_source: 'demo',
  },
)
// An old semantic result must never be reused by the keyword search.
client.setQueryData(['unified-movies', 'unified=true&page=1&page_size=20'], {
  items: [
    {
      id: 329865,
      title: 'Outdated semantic result',
      genres: [],
      source: 'demo',
      artwork_kind: 'placeholder',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
  total_pages: 1,
  data_source: 'demo',
})
function BrokenPage(): never {
  throw new Error('Private diagnostic must not appear in the recovery screen')
}
const router = createMemoryRouter([
  {
    path: '/',
    element: new URLSearchParams(location.search).has('broken') ? (
      <BrokenPage />
    ) : (
      <MovieSearch />
    ),
    errorElement: <RouteErrorPage />,
  },
])
createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={client}>
    <AuthProvider>
      <CollectionProvider>
        <RouterProvider router={router} />
      </CollectionProvider>
    </AuthProvider>
  </QueryClientProvider>,
)
