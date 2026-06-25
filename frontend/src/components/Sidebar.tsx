import { NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Plus, LogOut, Bot } from 'lucide-react'

export default function Sidebar() {
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <Bot size={22} />
        <span>ChatSaaS</span>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
        >
          <LayoutDashboard size={17} />
          <span>Dashboard</span>
        </NavLink>

        <NavLink
          to="/chatbots/new"
          className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
        >
          <Plus size={17} />
          <span>New Chatbot</span>
        </NavLink>
      </nav>

      <button className="sidebar-logout" onClick={logout}>
        <LogOut size={17} />
        <span>Logout</span>
      </button>
    </aside>
  )
}
