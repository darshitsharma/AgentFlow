import { useState, useEffect, useRef } from 'react';
import { Activity, Bot, MessageSquare, Zap, RefreshCw, Hash, ArrowRightLeft } from 'lucide-react';
import { AgentLog, logsApi } from '../api';

interface Stats {
    total_agents: number;
    active_agents: number;
    total_messages: number;
    total_tokens: number;
    messages_by_channel: Record<string, number>;
    messages_by_role: Record<string, number>;
    agent_stats: { id: string; name: string; tokens_used: number; message_count: number }[];
    recent_inter_agent: { id: string; agent_id: string; role: string; content: string; tokens_used: number; created_at: string }[];
}

export default function MonitorPage() {
    const [stats, setStats] = useState<Stats | null>(null);
    const [logs, setLogs] = useState<AgentLog[]>([]);
    const [autoRefresh, setAutoRefresh] = useState(true);
    const [tab, setTab] = useState<'overview' | 'logs' | 'inter-agent'>('overview');
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const loadData = async () => {
        try {
            const [s, l] = await Promise.all([
                logsApi.stats(),
                logsApi.recent(50),
            ]);
            setStats(s);
            setLogs(l);
        } catch (e) {
            console.error('Failed to load monitoring data', e);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    useEffect(() => {
        if (autoRefresh) {
            intervalRef.current = setInterval(loadData, 5000);
        }
        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [autoRefresh]);

    const channelColor = (ch: string) => {
        switch (ch) {
            case 'web': return 'bg-blue-900/50 text-blue-300';
            case 'telegram': return 'bg-cyan-900/50 text-cyan-300';
            case 'inter-agent': return 'bg-purple-900/50 text-purple-300';
            default: return 'bg-gray-700 text-gray-300';
        }
    };

    const levelColor = (level: string) => {
        switch (level) {
            case 'error': return 'text-red-400';
            case 'warning': return 'text-yellow-400';
            default: return 'text-green-400';
        }
    };

    return (
        <div className="p-8">
            <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold">Monitor</h2>
                <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
                        <input
                            type="checkbox"
                            checked={autoRefresh}
                            onChange={(e) => setAutoRefresh(e.target.checked)}
                            className="rounded"
                        />
                        Auto-refresh (5s)
                    </label>
                    <button onClick={loadData} className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs">
                        <RefreshCw size={14} /> Refresh
                    </button>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-6 bg-gray-800 rounded-lg p-1 w-fit">
                {(['overview', 'logs', 'inter-agent'] as const).map((t) => (
                    <button
                        key={t}
                        onClick={() => setTab(t)}
                        className={`px-4 py-1.5 rounded text-sm capitalize transition-colors ${tab === t ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'
                            }`}
                    >
                        {t === 'inter-agent' ? 'Inter-Agent' : t}
                    </button>
                ))}
            </div>

            {tab === 'overview' && stats && (
                <>
                    {/* Stat Cards */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                        <StatCard icon={<Bot size={20} />} label="Total Agents" value={stats.total_agents} sub={`${stats.active_agents} active`} color="blue" />
                        <StatCard icon={<MessageSquare size={20} />} label="Total Messages" value={stats.total_messages} color="green" />
                        <StatCard icon={<Zap size={20} />} label="Total Tokens" value={stats.total_tokens.toLocaleString()} color="yellow" />
                        <StatCard icon={<Hash size={20} />} label="Channels" value={Object.keys(stats.messages_by_channel).length} color="purple" />
                    </div>

                    {/* Messages by Channel */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
                            <h3 className="text-sm font-semibold text-gray-300 mb-3">Messages by Channel</h3>
                            <div className="space-y-2">
                                {Object.entries(stats.messages_by_channel).map(([ch, count]) => (
                                    <div key={ch} className="flex items-center justify-between">
                                        <span className={`px-2 py-0.5 rounded text-xs ${channelColor(ch)}`}>{ch}</span>
                                        <div className="flex items-center gap-2 flex-1 mx-3">
                                            <div className="flex-1 bg-gray-700 rounded-full h-2">
                                                <div
                                                    className="bg-blue-500 rounded-full h-2"
                                                    style={{ width: `${Math.min(100, (count / Math.max(stats.total_messages, 1)) * 100)}%` }}
                                                />
                                            </div>
                                        </div>
                                        <span className="text-sm text-gray-300 w-12 text-right">{count}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
                            <h3 className="text-sm font-semibold text-gray-300 mb-3">Messages by Role</h3>
                            <div className="space-y-2">
                                {Object.entries(stats.messages_by_role).map(([role, count]) => (
                                    <div key={role} className="flex items-center justify-between">
                                        <span className="text-xs text-gray-400 w-20">{role}</span>
                                        <div className="flex items-center gap-2 flex-1 mx-3">
                                            <div className="flex-1 bg-gray-700 rounded-full h-2">
                                                <div
                                                    className="bg-green-500 rounded-full h-2"
                                                    style={{ width: `${Math.min(100, (count / Math.max(stats.total_messages, 1)) * 100)}%` }}
                                                />
                                            </div>
                                        </div>
                                        <span className="text-sm text-gray-300 w-12 text-right">{count}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Per-Agent Token Usage */}
                    <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
                        <h3 className="text-sm font-semibold text-gray-300 mb-3">Agent Token Usage</h3>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-gray-400 text-xs border-b border-gray-700">
                                        <th className="text-left py-2 px-3">Agent</th>
                                        <th className="text-right py-2 px-3">Messages</th>
                                        <th className="text-right py-2 px-3">Tokens Used</th>
                                        <th className="text-right py-2 px-3">Est. Cost (Ollama)</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {stats.agent_stats.map((a) => (
                                        <tr key={a.id} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                                            <td className="py-2 px-3 font-medium">{a.name}</td>
                                            <td className="py-2 px-3 text-right text-gray-300">{a.message_count}</td>
                                            <td className="py-2 px-3 text-right text-gray-300">{a.tokens_used.toLocaleString()}</td>
                                            <td className="py-2 px-3 text-right text-green-400">$0.00 (local)</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </>
            )}

            {tab === 'logs' && (
                <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                    <div className="p-4 border-b border-gray-700">
                        <h3 className="text-sm font-semibold text-gray-300">Real-Time Logs</h3>
                    </div>
                    <div className="max-h-[600px] overflow-auto">
                        <table className="w-full text-xs">
                            <thead className="sticky top-0 bg-gray-800">
                                <tr className="text-gray-400 border-b border-gray-700">
                                    <th className="text-left py-2 px-3 w-40">Time</th>
                                    <th className="text-left py-2 px-3 w-16">Level</th>
                                    <th className="text-left py-2 px-3 w-48">Event</th>
                                    <th className="text-left py-2 px-3">Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map((log) => (
                                    <tr key={log.id} className="border-b border-gray-700/30 hover:bg-gray-700/20">
                                        <td className="py-1.5 px-3 text-gray-500">
                                            {new Date(log.created_at).toLocaleTimeString()}
                                        </td>
                                        <td className={`py-1.5 px-3 font-mono ${levelColor(log.level)}`}>
                                            {log.level}
                                        </td>
                                        <td className="py-1.5 px-3 text-gray-300">{log.event}</td>
                                        <td className="py-1.5 px-3 text-gray-500 max-w-md truncate">
                                            {JSON.stringify(log.details).substring(0, 120)}
                                        </td>
                                    </tr>
                                ))}
                                {logs.length === 0 && (
                                    <tr>
                                        <td colSpan={4} className="py-8 text-center text-gray-500">
                                            No logs yet. Run a workflow or chat with an agent to generate logs.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {tab === 'inter-agent' && stats && (
                <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                    <div className="p-4 border-b border-gray-700 flex items-center gap-2">
                        <ArrowRightLeft size={16} className="text-purple-400" />
                        <h3 className="text-sm font-semibold text-gray-300">Inter-Agent Messages</h3>
                    </div>
                    <div className="max-h-[600px] overflow-auto p-4 space-y-3">
                        {stats.recent_inter_agent.map((msg) => (
                            <div key={msg.id} className="bg-gray-900 rounded-lg p-3 border border-gray-700/50">
                                <div className="flex items-center justify-between mb-1">
                                    <span className="text-xs font-medium text-purple-300">
                                        {msg.role === 'user' ? '→ Input' : '← Response'} · Agent: {msg.agent_id.substring(0, 8)}...
                                    </span>
                                    <span className="text-[10px] text-gray-500">
                                        {msg.created_at ? new Date(msg.created_at).toLocaleTimeString() : ''}
                                        {msg.tokens_used > 0 && ` · ${msg.tokens_used} tokens`}
                                    </span>
                                </div>
                                <p className="text-sm text-gray-300">{msg.content}</p>
                            </div>
                        ))}
                        {stats.recent_inter_agent.length === 0 && (
                            <p className="text-sm text-gray-500 text-center py-8">
                                No inter-agent messages yet. Run a multi-agent workflow to see agent communication.
                            </p>
                        )}
                    </div>
                </div>
            )}

            {!stats && (
                <div className="text-center py-16 text-gray-500">Loading monitoring data...</div>
            )}
        </div>
    );
}

function StatCard({ icon, label, value, sub, color }: {
    icon: React.ReactNode;
    label: string;
    value: number | string;
    sub?: string;
    color: string;
}) {
    const colorMap: Record<string, string> = {
        blue: 'bg-blue-900/30 border-blue-800/50 text-blue-400',
        green: 'bg-green-900/30 border-green-800/50 text-green-400',
        yellow: 'bg-yellow-900/30 border-yellow-800/50 text-yellow-400',
        purple: 'bg-purple-900/30 border-purple-800/50 text-purple-400',
    };
    return (
        <div className={`rounded-xl p-4 border ${colorMap[color]}`}>
            <div className="flex items-center gap-2 mb-2 opacity-80">{icon}<span className="text-xs">{label}</span></div>
            <div className="text-2xl font-bold text-white">{value}</div>
            {sub && <div className="text-xs mt-1 opacity-60">{sub}</div>}
        </div>
    );
}
