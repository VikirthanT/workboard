import { Navigate, Route, Routes } from 'react-router-dom';
import { TeamsView } from '../features/admin';
import { LoginPage } from '../features/auth';
import { BoardView } from '../features/board';
import { TeamView } from '../features/team';
import { AppShell } from './components/AppShell';

/* Guards live at the route definition: AppShell redirects to /login without a session.
   Each view then checks what the signed-in user may see (admin portal, team, board) itself. */
export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        <Route index element={<BoardView />} />
        <Route path="boards" element={<BoardView adminView />} />
        <Route path="boards/:team" element={<BoardView adminView />} />
        <Route path="team" element={<TeamView />} />
        <Route path="admin" element={<TeamsView />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
