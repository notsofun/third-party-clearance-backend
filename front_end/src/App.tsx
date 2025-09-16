import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ReviewPage from './pages/Review';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<ReviewPage />} />
      </Routes>
    </Router>
  );
}

export default App;