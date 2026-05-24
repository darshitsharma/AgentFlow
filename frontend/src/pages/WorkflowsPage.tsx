import { useState, useEffect, useCallback } from 'react';
import ReactFlow, {
    Node,
    Edge,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    MarkerType,
    Panel,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { Plus, Play, Save, Trash2, FileText, ChevronDown, Maximize2, Minimize2, X, Code, AlignLeft, List, MessageCircle } from 'lucide-react';
import { Agent, Workflow, agentsApi, workflowsApi, executionApi } from '../api';

const TEMPLATES = {
    research_summarize: {
        name: 'Research & Summarize',
        description: 'A researcher agent gathers info, then a summarizer condenses it for human review.',
        graph: {
            nodes: [
                { id: 'n1', type: 'default', position: { x: 100, y: 100 }, data: { label: 'Researcher', agent_id: '', role: 'researcher' } },
                { id: 'n2', type: 'default', position: { x: 400, y: 100 }, data: { label: 'Summarizer', agent_id: '', role: 'summarizer' } },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2', markerEnd: { type: MarkerType.ArrowClosed }, label: 'always' },
            ],
        },
    },
    support_escalation: {
        name: 'Customer Support Escalation',
        description: 'Frontline bot handles queries; if unable, escalates to specialist; if still unresolved, notifies manager.',
        graph: {
            nodes: [
                { id: 'n1', type: 'default', position: { x: 100, y: 150 }, data: { label: 'Frontline Bot', agent_id: '', role: 'frontline' } },
                { id: 'n2', type: 'default', position: { x: 400, y: 50 }, data: { label: 'Specialist', agent_id: '', role: 'specialist' } },
                { id: 'n3', type: 'default', position: { x: 700, y: 150 }, data: { label: 'Manager', agent_id: '', role: 'manager' } },
            ],
            edges: [
                { id: 'e1', source: 'n1', target: 'n2', markerEnd: { type: MarkerType.ArrowClosed }, label: 'escalate', data: { condition: { type: 'contains', value: 'ESCALATE' } } },
                { id: 'e2', source: 'n2', target: 'n3', markerEnd: { type: MarkerType.ArrowClosed }, label: 'unresolved', data: { condition: { type: 'contains', value: 'ESCALATE' } } },
            ],
        },
    },
};

export default function WorkflowsPage() {
    const [agents, setAgents] = useState<Agent[]>([]);
    const [workflows, setWorkflows] = useState<Workflow[]>([]);
    const [selectedWorkflow, setSelectedWorkflow] = useState<Workflow | null>(null);
    const [workflowName, setWorkflowName] = useState('');
    const [workflowDesc, setWorkflowDesc] = useState('');
    const [nodes, setNodes, onNodesChange] = useNodesState([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);
    const [showList, setShowList] = useState(true);
    const [runInput, setRunInput] = useState('');
    const [runResult, setRunResult] = useState<any>(null);
    const [running, setRunning] = useState(false);
    const [selectedNode, setSelectedNode] = useState<Node | null>(null);
    const [edgeCondition, setEdgeCondition] = useState<{ edgeId: string; type: string; value: string } | null>(null);
    const [statusBar, setStatusBar] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
    const [outputExpanded, setOutputExpanded] = useState(false);
    const [outputView, setOutputView] = useState<'formatted' | 'json' | 'steps'>('formatted');
    const [telegramEnabled, setTelegramEnabled] = useState(false);

    useEffect(() => {
        agentsApi.list().then(setAgents);
        loadWorkflows();
    }, []);

    const loadWorkflows = () => workflowsApi.list().then(setWorkflows);

    const onConnect = useCallback(
        (params: Connection) =>
            setEdges((eds) =>
                addEdge({ ...params, markerEnd: { type: MarkerType.ArrowClosed }, label: 'always', data: { condition: null } }, eds)
            ),
        [setEdges]
    );

    const addNode = () => {
        const id = `n_${Date.now()}`;
        const newNode: Node = {
            id,
            type: 'default',
            position: { x: 200 + Math.random() * 200, y: 100 + Math.random() * 200 },
            data: { label: 'New Agent Node', agent_id: '', role: '' },
        };
        setNodes((ns) => [...ns, newNode]);
    };

    const loadTemplate = (key: string) => {
        const tmpl = TEMPLATES[key as keyof typeof TEMPLATES];
        if (!tmpl) return;
        setWorkflowName(tmpl.name);
        setWorkflowDesc(tmpl.description);
        setNodes(tmpl.graph.nodes);
        setEdges(tmpl.graph.edges as Edge[]);
        setSelectedWorkflow(null);
        setShowList(false);
    };

    const buildGraphPayload = () => ({
        nodes: nodes.map((n) => ({
            id: n.id,
            agent_id: n.data.agent_id,
            label: n.data.label,
            position: n.position,
        })),
        edges: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            condition: e.data?.condition || null,
        })),
    });

    const handleSave = async () => {
        try {
            const graph = buildGraphPayload();
            const channels = telegramEnabled ? ['telegram'] : [];
            if (selectedWorkflow) {
                await workflowsApi.update(selectedWorkflow.id, { name: workflowName, description: workflowDesc, graph, channels });
            } else {
                await workflowsApi.create({ name: workflowName || 'Untitled Workflow', description: workflowDesc, graph, channels });
            }
            await loadWorkflows();
            setShowList(true);
            setStatusBar({ message: `Workflow "${workflowName || 'Untitled Workflow'}" saved successfully.`, type: 'success' });
            setTimeout(() => setStatusBar(null), 4000);
        } catch (e: any) {
            setStatusBar({ message: e?.response?.data?.detail || e?.message || 'Failed to save workflow.', type: 'error' });
            setTimeout(() => setStatusBar(null), 6000);
        }
    };

    const handleOpen = (wf: Workflow) => {
        setSelectedWorkflow(wf);
        setWorkflowName(wf.name);
        setWorkflowDesc(wf.description);
        setTelegramEnabled((wf.channels || []).includes('telegram'));

        const g = wf.graph as any;
        const loadedNodes = (g.nodes || []).map((n: any) => ({
            id: n.id,
            type: 'default',
            position: n.position || { x: 100, y: 100 },
            data: { label: n.label || 'Agent', agent_id: n.agent_id || '', role: n.role || '' },
        }));
        const loadedEdges = (g.edges || []).map((e: any) => ({
            id: e.id,
            source: e.source,
            target: e.target,
            markerEnd: { type: MarkerType.ArrowClosed },
            label: e.condition ? e.condition.type : 'always',
            data: { condition: e.condition },
        }));
        setNodes(loadedNodes);
        setEdges(loadedEdges);
        setShowList(false);
        setRunResult(null);
    };

    const handleRun = async () => {
        if (!selectedWorkflow || running) return;
        setRunning(true);
        setRunResult(null);
        try {
            const res = await executionApi.start(selectedWorkflow.id, { message: runInput || 'Execute the workflow' });
            setRunResult(res);
            setOutputExpanded(true);
            setOutputView('formatted');
        } catch (e: any) {
            setRunResult({ status: 'failed', output_data: { error: e.message } });
        } finally {
            setRunning(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this workflow?')) return;
        await workflowsApi.delete(id);
        loadWorkflows();
        if (selectedWorkflow?.id === id) {
            setSelectedWorkflow(null);
            setShowList(true);
        }
    };

    const onNodeClick = (_: any, node: Node) => setSelectedNode(node);

    const updateNodeAgent = (nodeId: string, agentId: string) => {
        const agent = agents.find((a) => a.id === agentId);
        setNodes((ns) =>
            ns.map((n) =>
                n.id === nodeId
                    ? { ...n, data: { ...n.data, agent_id: agentId, label: agent?.name || n.data.label } }
                    : n
            )
        );
    };

    const onEdgeClick = (_: any, edge: Edge) => {
        const cond = edge.data?.condition;
        setEdgeCondition({
            edgeId: edge.id,
            type: cond?.type || '',
            value: cond?.value?.toString() || '',
        });
    };

    const saveEdgeCondition = () => {
        if (!edgeCondition) return;
        const condition = edgeCondition.type
            ? { type: edgeCondition.type, value: edgeCondition.value }
            : null;
        setEdges((eds) =>
            eds.map((e) =>
                e.id === edgeCondition.edgeId
                    ? { ...e, label: condition ? condition.type : 'always', data: { condition } }
                    : e
            )
        );
        setEdgeCondition(null);
    };

    // Workflow list view
    if (showList) {
        return (
            <div className="p-8">
                {statusBar && (
                    <div className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium flex items-center justify-between ${statusBar.type === 'success' ? 'bg-green-900/50 text-green-300 border border-green-700' : 'bg-red-900/50 text-red-300 border border-red-700'
                        }`}>
                        <span>{statusBar.message}</span>
                        <button onClick={() => setStatusBar(null)} className="ml-4 text-current opacity-60 hover:opacity-100">✕</button>
                    </div>
                )}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-2xl font-bold">Workflows</h2>
                    <div className="flex gap-2">
                        <button
                            onClick={() => {
                                setSelectedWorkflow(null);
                                setWorkflowName('');
                                setWorkflowDesc('');
                                setTelegramEnabled(false);
                                setNodes([]);
                                setEdges([]);
                                setShowList(false);
                            }}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium"
                        >
                            <Plus size={16} /> New Workflow
                        </button>
                    </div>
                </div>

                {/* Templates */}
                <div className="mb-8">
                    <h3 className="text-lg font-semibold mb-3 text-gray-300">Templates</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries(TEMPLATES).map(([key, tmpl]) => (
                            <div
                                key={key}
                                onClick={() => loadTemplate(key)}
                                className="bg-gray-800 rounded-xl p-5 border border-gray-700 hover:border-blue-500 cursor-pointer transition-colors"
                            >
                                <div className="flex items-center gap-2 mb-2">
                                    <FileText size={18} className="text-blue-400" />
                                    <h4 className="font-semibold">{tmpl.name}</h4>
                                </div>
                                <p className="text-sm text-gray-400">{tmpl.description}</p>
                                <p className="text-xs text-gray-500 mt-2">{tmpl.graph.nodes.length} agents · {tmpl.graph.edges.length} connections</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Saved Workflows */}
                <h3 className="text-lg font-semibold mb-3 text-gray-300">Saved Workflows</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {workflows.map((wf) => (
                        <div key={wf.id} className="bg-gray-800 rounded-xl p-5 border border-gray-700 hover:border-gray-600 transition-colors">
                            <div className="flex items-center gap-2 mb-1">
                                <h4 className="font-semibold">{wf.name}</h4>
                                {(wf.channels || []).includes('telegram') && (
                                    <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-900/50 border border-blue-700 rounded-full text-[10px] text-blue-300">
                                        <MessageCircle size={10} /> Telegram
                                    </span>
                                )}
                            </div>
                            <p className="text-sm text-gray-400 mb-3">{wf.description || 'No description'}</p>
                            <div className="flex gap-2">
                                <button onClick={() => handleOpen(wf)} className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded text-xs">Open</button>
                                <button onClick={() => handleDelete(wf.id)} className="px-3 py-1.5 bg-red-900/50 hover:bg-red-800 rounded text-xs text-red-300">
                                    <Trash2 size={12} />
                                </button>
                            </div>
                        </div>
                    ))}
                    {workflows.length === 0 && (
                        <p className="text-sm text-gray-500 col-span-full">No saved workflows yet. Use a template or create a new one.</p>
                    )}
                </div>
            </div>
        );
    }

    // Workflow builder view
    return (
        <div className="flex flex-col h-full">
            {/* Toolbar */}
            <div className="p-3 border-b border-gray-700 flex items-center gap-3">
                <button onClick={() => setShowList(true)} className="text-sm text-gray-400 hover:text-white">← Back</button>
                <input
                    value={workflowName}
                    onChange={(e) => setWorkflowName(e.target.value)}
                    placeholder="Workflow Name"
                    className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm w-48 focus:outline-none focus:border-blue-500"
                />
                <button onClick={addNode} className="flex items-center gap-1 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-xs">
                    <Plus size={14} /> Add Node
                </button>
                <button onClick={handleSave} className="flex items-center gap-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 rounded text-xs">
                    <Save size={14} /> Save
                </button>
                <button
                    onClick={() => setTelegramEnabled(!telegramEnabled)}
                    className={`flex items-center gap-1 px-3 py-1.5 rounded text-xs border transition-colors ${telegramEnabled ? 'bg-blue-600 border-blue-500 text-white' : 'bg-gray-700 border-gray-600 text-gray-300 hover:bg-gray-600'}`}
                    title={telegramEnabled ? 'Connected to Telegram — click to disconnect' : 'Click to connect this workflow to Telegram'}
                >
                    <MessageCircle size={14} /> {telegramEnabled ? 'Telegram ✓' : 'Telegram'}
                </button>
                {selectedWorkflow && (
                    <>
                        <input
                            value={runInput}
                            onChange={(e) => setRunInput(e.target.value)}
                            placeholder="Workflow input message..."
                            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm flex-1 focus:outline-none focus:border-blue-500"
                        />
                        <button
                            onClick={handleRun}
                            disabled={running}
                            className="flex items-center gap-1 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded text-xs"
                        >
                            <Play size={14} /> {running ? 'Running...' : 'Run'}
                        </button>
                    </>
                )}
            </div>

            <div className="flex flex-1 min-h-0">
                {/* Canvas */}
                <div className="flex-1">
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        onNodeClick={onNodeClick}
                        onEdgeClick={onEdgeClick}
                        fitView
                        className="bg-gray-900"
                    >
                        <Controls className="!bg-gray-800 !border-gray-700" />
                        <Background color="#374151" gap={20} />
                    </ReactFlow>
                </div>

                {/* Side Panel */}
                <div className="w-72 bg-gray-800 border-l border-gray-700 overflow-auto p-4 space-y-4">
                    {/* Node config */}
                    {selectedNode && (
                        <div>
                            <h4 className="text-sm font-semibold mb-2 text-gray-300">Node Settings</h4>
                            <label className="block text-xs text-gray-400 mb-1">Assign Agent</label>
                            <select
                                value={selectedNode.data.agent_id || ''}
                                onChange={(e) => {
                                    updateNodeAgent(selectedNode.id, e.target.value);
                                    setSelectedNode({ ...selectedNode, data: { ...selectedNode.data, agent_id: e.target.value } });
                                }}
                                className="w-full px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm"
                            >
                                <option value="">Select agent...</option>
                                {agents.map((a) => (
                                    <option key={a.id} value={a.id}>{a.name} ({a.role})</option>
                                ))}
                            </select>
                            <button
                                onClick={() => {
                                    setNodes((ns) => ns.filter((n) => n.id !== selectedNode.id));
                                    setEdges((es) => es.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
                                    setSelectedNode(null);
                                }}
                                className="mt-2 px-3 py-1 bg-red-900/50 hover:bg-red-800 rounded text-xs text-red-300 w-full"
                            >
                                Delete Node
                            </button>
                        </div>
                    )}

                    {/* Edge condition editor */}
                    {edgeCondition && (
                        <div>
                            <h4 className="text-sm font-semibold mb-2 text-gray-300">Edge Condition</h4>
                            <label className="block text-xs text-gray-400 mb-1">Type</label>
                            <select
                                value={edgeCondition.type}
                                onChange={(e) => setEdgeCondition({ ...edgeCondition, type: e.target.value })}
                                className="w-full px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm mb-2"
                            >
                                <option value="">Always (no condition)</option>
                                <option value="contains">Contains</option>
                                <option value="not_contains">Not Contains</option>
                                <option value="max_iterations">Max Iterations</option>
                            </select>
                            {edgeCondition.type && (
                                <>
                                    <label className="block text-xs text-gray-400 mb-1">Value</label>
                                    <input
                                        value={edgeCondition.value}
                                        onChange={(e) => setEdgeCondition({ ...edgeCondition, value: e.target.value })}
                                        placeholder={edgeCondition.type === 'max_iterations' ? 'e.g. 3' : 'e.g. APPROVE'}
                                        className="w-full px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm mb-2"
                                    />
                                </>
                            )}
                            <div className="flex gap-2">
                                <button onClick={saveEdgeCondition} className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-xs">Apply</button>
                                <button onClick={() => setEdgeCondition(null)} className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs">Cancel</button>
                            </div>
                        </div>
                    )}

                    {/* Execution result - inline preview */}
                    {runResult && !outputExpanded && (
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <h4 className="text-sm font-semibold text-gray-300">Output</h4>
                                <button onClick={() => setOutputExpanded(true)} className="text-gray-400 hover:text-white" title="Expand">
                                    <Maximize2 size={14} />
                                </button>
                            </div>
                            <div className={`px-3 py-2 rounded text-xs mb-2 ${runResult.status === 'completed' ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
                                Status: {runResult.status}
                            </div>
                            {runResult.output_data?.result && (
                                <p className="text-xs text-gray-300 bg-gray-900 p-2 rounded line-clamp-4">{runResult.output_data.result}</p>
                            )}
                        </div>
                    )}

                    {/* Instructions */}
                    <div className="text-xs text-gray-500 space-y-1 pt-4 border-t border-gray-700">
                        <p>• Drag nodes to reposition</p>
                        <p>• Drag from handle to handle to connect</p>
                        <p>• Click a node to assign an agent</p>
                        <p>• Click an edge to set conditions</p>
                    </div>
                </div>
            </div>

            {/* Expanded Output Panel (overlay) */}
            {runResult && outputExpanded && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
                    <div className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl w-[90vw] h-[85vh] flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-700">
                            <div className="flex items-center gap-3">
                                <h3 className="text-lg font-semibold">Workflow Output</h3>
                                <div className={`px-2 py-0.5 rounded text-xs font-medium ${runResult.status === 'completed' ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
                                    {runResult.status}
                                </div>
                                {runResult.output_data?.total_steps != null && (
                                    <span className="text-xs text-gray-400">{runResult.output_data.total_steps} step(s)</span>
                                )}
                            </div>
                            <div className="flex items-center gap-2">
                                {/* View mode toggles */}
                                <div className="flex bg-gray-900 rounded-lg p-0.5">
                                    <button
                                        onClick={() => setOutputView('formatted')}
                                        className={`flex items-center gap-1 px-3 py-1 rounded text-xs transition-colors ${outputView === 'formatted' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                                    >
                                        <AlignLeft size={12} /> Formatted
                                    </button>
                                    <button
                                        onClick={() => setOutputView('json')}
                                        className={`flex items-center gap-1 px-3 py-1 rounded text-xs transition-colors ${outputView === 'json' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                                    >
                                        <Code size={12} /> JSON
                                    </button>
                                    <button
                                        onClick={() => setOutputView('steps')}
                                        className={`flex items-center gap-1 px-3 py-1 rounded text-xs transition-colors ${outputView === 'steps' ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white'}`}
                                    >
                                        <List size={12} /> Steps
                                    </button>
                                </div>
                                <button onClick={() => setOutputExpanded(false)} className="text-gray-400 hover:text-white p-1">
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        {/* Body */}
                        <div className="flex-1 overflow-auto p-5">
                            {outputView === 'formatted' && (
                                <div className="max-w-none space-y-4">
                                    {runResult.output_data?.result ? (
                                        (() => {
                                            const text: string = runResult.output_data.result;
                                            // Check if output has agent sections (--- Agent Name ---)
                                            const sections = text.split(/^--- (.+?) ---$/m);
                                            if (sections.length > 1) {
                                                const cards: { name: string; content: string }[] = [];
                                                // sections: ['prefix', 'Name1', 'content1', 'Name2', 'content2', ...]
                                                for (let i = 1; i < sections.length; i += 2) {
                                                    cards.push({ name: sections[i], content: (sections[i + 1] || '').trim() });
                                                }
                                                return (
                                                    <div className="space-y-4">
                                                        {cards.map((card, idx) => (
                                                            <div key={idx} className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
                                                                <div className="px-4 py-2.5 bg-gray-800 border-b border-gray-700 flex items-center gap-2">
                                                                    <div className="w-2 h-2 rounded-full bg-blue-400"></div>
                                                                    <span className="text-sm font-semibold text-gray-200">{card.name}</span>
                                                                </div>
                                                                <div className="p-4 text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">
                                                                    {card.content}
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                );
                                            }
                                            // Single output — render as clean text
                                            return (
                                                <div className="bg-gray-900 rounded-xl border border-gray-700 p-5">
                                                    <div className="whitespace-pre-wrap text-sm text-gray-200 leading-relaxed">
                                                        {text}
                                                    </div>
                                                </div>
                                            );
                                        })()
                                    ) : runResult.output_data?.error ? (
                                        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300">
                                            <p className="font-semibold mb-1">Error</p>
                                            <p className="text-sm">{runResult.output_data.error}</p>
                                        </div>
                                    ) : (
                                        <p className="text-gray-500">No output data.</p>
                                    )}
                                </div>
                            )}

                            {outputView === 'json' && (
                                <pre className="text-xs bg-gray-900 p-4 rounded-lg overflow-auto text-green-300 font-mono leading-relaxed">
                                    {JSON.stringify(runResult, null, 2)}
                                </pre>
                            )}

                            {outputView === 'steps' && (
                                <div className="space-y-3">
                                    {(runResult.output_data?.steps || runResult.steps || []).length > 0 ? (
                                        (runResult.output_data?.steps || runResult.steps || []).map((step: any, i: number) => (
                                            <div key={i} className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span className="w-6 h-6 flex items-center justify-center bg-blue-600 rounded-full text-xs font-bold">{i + 1}</span>
                                                    <span className="text-sm font-medium text-gray-200">
                                                        {step.agent_name || step.node_id || `Step ${i + 1}`}
                                                    </span>
                                                    <span className={`ml-auto text-xs px-2 py-0.5 rounded ${step.status === 'completed' || step.status === 'success' ? 'bg-green-900/50 text-green-300' : 'bg-red-900/50 text-red-300'}`}>
                                                        {step.status || 'done'}
                                                    </span>
                                                    {step.tokens != null && (
                                                        <span className="text-xs text-gray-500">{step.tokens} tokens</span>
                                                    )}
                                                </div>
                                                {step.output && (
                                                    <div className="text-sm text-gray-300 whitespace-pre-wrap bg-gray-800 rounded p-3 mt-1">
                                                        {step.output}
                                                    </div>
                                                )}
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-gray-500 text-sm">
                                            <p className="mb-2">No step-by-step data available. Showing full output:</p>
                                            <pre className="text-xs bg-gray-900 p-4 rounded-lg overflow-auto text-gray-300 font-mono">
                                                {JSON.stringify(runResult.output_data, null, 2)}
                                            </pre>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
