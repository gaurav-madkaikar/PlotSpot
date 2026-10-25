import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createBrowserRouter,
  RouterProvider,
  Navigate,
  useLocation,
} from 'react-router'
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/libre-bodoni/latin-400.css'
import '@fontsource/libre-bodoni/latin-400-italic.css'
import './styles.css'
import { CollectionProvider } from './lib/collection'
import { AuthProvider, useAuth } from './lib/auth'
import { Shell } from './components/shell'
import { LoadingPage, MissingMovie } from './components/status-panel'
import { RouteErrorPage } from './components/route-error-page'
import { DiscoverPage } from './pages/discover'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, retry: 1 } },
})
const labEnabled =
  import.meta.env.DEV && import.meta.env.VITE_PLOTSPOT_LAB_ENABLED === 'true'

function LegacyCollectionRoute() {
  const location = useLocation()
  return (
    <Navigate
      to={{
        pathname: '/collections',
        search: location.search,
        hash: location.hash,
      }}
      state={location.state}
      replace
    />
  )
}

const router = createBrowserRouter([
  {
    element: <Shell />,
    errorElement: <RouteErrorPage />,
    hydrateFallbackElement: <LoadingPage />,
    children: [
      { path: '/', element: <DiscoverPage /> },
      {
        path: '/movies/:movieId',
        lazy: async () => ({
          Component: (await import('./pages/movie')).MoviePage,
        }),
      },
      {
        path: '/collections',
        lazy: async () => ({
          Component: (await import('./pages/collection')).CollectionPage,
        }),
      },
      {
        path: '/about',
        lazy: async () => ({
          Component: (await import('./pages/about')).AboutPage,
        }),
      },
      {
        path: '/account',
        lazy: async () => ({
          Component: (await import('./pages/account')).AccountPage,
        }),
      },
      ...(labEnabled
        ? [
            {
              path: '/lab',
              lazy: async () => ({
                Component: (await import('./pages/lab')).LabPage,
              }),
            },
          ]
        : []),
      { path: '/collection', element: <LegacyCollectionRoute /> },
      { path: '*', element: <MissingMovie /> },
    ],
  },
])

function PersonalApp() {
  const { user } = useAuth()
  return (
    <CollectionProvider key={user?.id ?? 'guest'}>
      <RouterProvider router={router} />
    </CollectionProvider>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <PersonalApp />
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
)
