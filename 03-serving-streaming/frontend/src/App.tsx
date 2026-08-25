import { Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Watch } from './pages/Watch'
import { Upload } from './pages/Upload'
import { Studio } from './pages/Studio'
import { Recommended } from './pages/Recommended'
import { Channel } from './pages/Channel'
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'
import { NotFound } from './pages/NotFound'

function App() {
  return (
    <Routes>
      {/* fora do Layout: feed de tela cheia, sem navbar, estilo Reels */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Recommended />
          </ProtectedRoute>
        }
      />
      <Route element={<Layout />}>
        <Route path="/watch/:videoId" element={<Watch />} />
        <Route path="/channel/:channelId" element={<Channel />} />
        <Route path="/sign-in/*" element={<SignInPage />} />
        <Route path="/sign-up/*" element={<SignUpPage />} />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <Upload />
            </ProtectedRoute>
          }
        />
        <Route
          path="/studio"
          element={
            <ProtectedRoute>
              <Studio />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default App
