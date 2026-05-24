import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Bot, Workflow, MessageSquare, Activity } from 'lucide-react';
import AgentsPage from './pages/AgentsPage';
import WorkflowsPage from './pages/WorkflowsPage';
import ChatPage from './pages/ChatPage';
import MonitorPage from './pages/MonitorPage';

function App() {
    return (
        <BrowserRouter>
            <div className="flex h-screen">
                {/* Sidebar */}
                <nav className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
                    <div className="p-4 border-b border-gray-700">
                        <h1 className="text-xl font-bold text-blue-400">🤖 AgentFlow</h1>
                        <p className="text-xs text-gray-400 mt-1">AI Agent Orchestration</p>
                    </div>
                    <div className="flex-1 p-3 space-y-1">
                        <SidebarLink to="/agents" icon={<Bot size={18} />} label="Agents" />
                        <SidebarLink to="/workflows" icon={<Workflow size={18} />} label="Workflows" />
                        <SidebarLink to="/chat" icon={<MessageSquare size={18} />} label="Chat" />
                        <SidebarLink to="/monitor" icon={<Activity size={18} />} label="Monitor" />
                    </div>
                </nav>

                {/* Main Content */}
                <main className="flex-1 overflow-auto bg-gray-900">
                    <Routes>
                        <Route path="/" element={<AgentsPage />} />
                        <Route path="/agents" element={<AgentsPage />} />
                        <Route path="/workflows" element={<WorkflowsPage />} />
                        <Route path="/chat" element={<ChatPage />} />
                        <Route path="/monitor" element={<MonitorPage />} />
                    </Routes>
                </main>
            </div>
        </BrowserRouter>
    );
}

function SidebarLink({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
    return (
        <NavLink
            to={to}
            className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${isActive ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700'
                }`
            }
        >
            {icon}
            <span className="text-sm font-medium">{label}</span>
        </NavLink>
    );
}

export default App;
