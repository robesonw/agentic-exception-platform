import React, { useState, useEffect, useRef } from 'react';
import { 
  LayoutDashboard, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  Search, 
  Bell, 
  Settings, 
  Menu, 
  ChevronRight, 
  ChevronDown, 
  Bot, 
  FileText, 
  Zap, 
  BarChart3, 
  Layers, 
  Workflow, 
  MoreHorizontal,
  ArrowUpRight,
  ShieldAlert,
  BrainCircuit,
  Database,
  Share2,
  X,
  MessageSquare,
  PlayCircle,
  History,
  Send,
  Cpu,
  Filter,
  RefreshCw
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer, 
  AreaChart, 
  Area 
} from 'recharts';

// --- Mock Data ---

const MOCK_EXCEPTIONS = [
  { id: 'EX-2025-8901', type: 'Trade Settlement Failure', domain: 'Capital Markets', severity: 'Critical', score: 98, status: 'Open', owner: 'AI Agent (L1)', created: '2 mins ago', entity: 'Goldman Sachs', amount: '$4.2M' },
  { id: 'EX-2025-8902', type: 'Duplicate Claim Detected', domain: 'Healthcare', severity: 'High', score: 85, status: 'Analyzing', owner: 'AI Agent (L2)', created: '5 mins ago', entity: 'Memorial Hospital', amount: '$12,500' },
  { id: 'EX-2025-8903', type: 'KYC Mismatch', domain: 'Banking', severity: 'Medium', score: 62, status: 'Human Review', owner: 'Sarah J.', created: '12 mins ago', entity: 'John Doe', amount: 'N/A' },
  { id: 'EX-2025-8904', type: 'Reconciliation Break', domain: 'Finance', severity: 'Low', score: 45, status: 'Resolved', owner: 'Auto-Resolved', created: '1 hour ago', entity: 'Ledger A/B', amount: '$150.00' },
  { id: 'EX-2025-8905', type: 'Margin Call Warning', domain: 'Trading', severity: 'Critical', score: 92, status: 'Open', owner: 'AI Agent (L1)', created: '1 hour ago', entity: 'Hedge Fund X', amount: '$1.5M' },
];

const ANALYTICS_DATA = [
  { time: '09:00', volume: 45, auto: 40, human: 5 },
  { time: '10:00', volume: 120, auto: 105, human: 15 },
  { time: '11:00', volume: 85, auto: 78, human: 7 },
  { time: '12:00', volume: 60, auto: 55, human: 5 },
  { time: '13:00', volume: 150, auto: 130, human: 20 },
  { time: '14:00', volume: 95, auto: 88, human: 7 },
];

const AGENT_THOUGHTS = [
  { step: 1, action: 'Ingest', detail: 'Received settlement failure msg from SWIFT network.', status: 'complete', time: '10:42:01 AM' },
  { step: 2, action: 'Classify', detail: 'Identified as "Currency Mismatch" with 98% confidence.', status: 'complete', time: '10:42:02 AM' },
  { step: 3, action: 'RAG Search', detail: 'Retrieved 3 similar cases from Q3 2024 (Policy Pack v2.1).', status: 'complete', time: '10:42:03 AM' },
  { step: 4, action: 'Reasoning', detail: 'Mismatch is due to EUR/USD holiday calendar variance.', status: 'processing', time: 'Now' },
];

// --- Components ---

const StatusBadge = ({ status, severity }) => {
  let colorClass = 'bg-slate-700 text-slate-300';
  if (severity === 'Critical') colorClass = 'bg-red-900/40 text-red-400 border border-red-800/50';
  else if (severity === 'High') colorClass = 'bg-orange-900/40 text-orange-400 border border-orange-800/50';
  else if (status === 'Resolved' || status === 'Auto-Resolved') colorClass = 'bg-emerald-900/40 text-emerald-400 border border-emerald-800/50';
  else if (status === 'Analyzing') colorClass = 'bg-blue-900/40 text-blue-400 border border-blue-800/50 animate-pulse';

  return (
    <span className={`px-2.5 py-1 rounded text-xs font-medium tracking-wide ${colorClass}`}>
      {status || severity}
    </span>
  );
};

const AICopilot = ({ onClose }) => {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'Hello, Operator. I am monitoring 4 active critical exceptions. How can I assist you today?' }
  ]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const handleSend = () => {
    if (!input.trim()) return;
    const newMsgs = [...messages, { role: 'user', text: input }];
    setMessages(newMsgs);
    setInput('');
    setTimeout(() => {
      setMessages([...newMsgs, { role: 'ai', text: 'I am analyzing the correlation between the recent trade failures and the SWIFT gateway latency. One moment...' }]);
    }, 1000);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[600px] bg-[#0f1219] border border-slate-700 shadow-2xl rounded-xl flex flex-col z-50 overflow-hidden font-sans">
      <div className="bg-[#1a1f2e] p-4 border-b border-slate-700 flex justify-between items-center">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="font-semibold text-slate-100 flex items-center gap-2">
             <Bot size={16} className="text-blue-400" /> AI Co-Pilot
          </span>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-white"><X size={16} /></button>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-[#0B0E14]">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-3 rounded-lg text-sm ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-300 border border-slate-700'}`}>
              {msg.text}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-[#1a1f2e] border-t border-slate-700">
        <div className="flex gap-2">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Ask about exceptions, trends, or rules..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500 placeholder-slate-500"
          />
          <button onClick={handleSend} className="bg-blue-600 hover:bg-blue-500 text-white p-2 rounded-md transition-colors">
            <Send size={16} />
          </button>
        </div>
        <div className="mt-2 flex gap-2 overflow-x-auto pb-1">
          {['Summarize risks', 'Draft response', 'Show similar cases'].map(suggestion => (
            <button key={suggestion} className="whitespace-nowrap px-2 py-1 bg-slate-800 hover:bg-slate-700 border border-slate-600 rounded text-xs text-slate-400 transition-colors">
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

const ExceptionsTable = ({ onSelectException }) => {
  return (
    <div className="bg-[#151A23] border border-slate-800 rounded-lg overflow-hidden shadow-sm">
      <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-[#151A23]">
        <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
          <ShieldAlert size={18} className="text-blue-400" /> Active Exceptions
        </h3>
        <div className="flex gap-2">
           <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded border border-slate-700 transition-colors">
            <Filter size={14} /> Filter
          </button>
          <button className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm rounded border border-slate-700 transition-colors">
            <ArrowUpRight size={14} /> Export
          </button>
        </div>
      </div>
      <table className="w-full text-left text-sm text-slate-400">
        <thead className="bg-[#1a1f2e] text-slate-200 uppercase text-xs font-semibold tracking-wider">
          <tr>
            <th className="px-6 py-3">ID / Time</th>
            <th className="px-6 py-3">Domain</th>
            <th className="px-6 py-3">Type</th>
            <th className="px-6 py-3">Entity</th>
            <th className="px-6 py-3">AI Confidence</th>
            <th className="px-6 py-3">Severity</th>
            <th className="px-6 py-3 text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/50">
          {MOCK_EXCEPTIONS.map((ex) => (
            <tr 
              key={ex.id} 
              onClick={() => onSelectException(ex)}
              className="hover:bg-slate-800/50 cursor-pointer transition-colors group"
            >
              <td className="px-6 py-4">
                <div className="font-medium text-blue-400 group-hover:text-blue-300">{ex.id}</div>
                <div className="text-xs text-slate-500 mt-0.5">{ex.created}</div>
              </td>
              <td className="px-6 py-4 text-slate-300">{ex.domain}</td>
              <td className="px-6 py-4 text-slate-300">{ex.type}</td>
              <td className="px-6 py-4 text-slate-300 font-mono">{ex.entity}</td>
              <td className="px-6 py-4">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-500" style={{ width: `${ex.score}%` }}></div>
                  </div>
                  <span className="text-xs text-slate-400">{ex.score}%</span>
                </div>
              </td>
              <td className="px-6 py-4">
                <StatusBadge severity={ex.severity} />
              </td>
              <td className="px-6 py-4 text-right">
                <button className="p-1 hover:bg-slate-700 rounded text-slate-400">
                  <MoreHorizontal size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

const ExceptionDetail = ({ exception, onBack }) => {
  return (
    <div className="h-full flex flex-col animate-in fade-in slide-in-from-right-4 duration-300">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-4">
          <button onClick={onBack} className="p-2 hover:bg-slate-800 rounded-full text-slate-400 transition-colors">
            <X size={20} />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              {exception.id} 
              <StatusBadge severity={exception.severity} />
            </h1>
            <p className="text-slate-400 text-sm mt-1 flex items-center gap-4">
              <span>{exception.type}</span>
              <span className="w-1 h-1 bg-slate-600 rounded-full"></span>
              <span>{exception.domain}</span>
              <span className="w-1 h-1 bg-slate-600 rounded-full"></span>
              <span className="text-slate-500">Owner: {exception.owner}</span>
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-red-900/30 hover:bg-red-900/50 text-red-400 text-sm font-medium rounded-lg border border-red-900/50 transition-colors">
            <AlertCircle size={16} /> Escalate
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg shadow-lg shadow-blue-900/20 transition-colors">
            <CheckCircle2 size={16} /> Approve Resolution
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 flex-1 overflow-hidden">
        {/* Left: Context & Evidence */}
        <div className="col-span-3 space-y-6 overflow-y-auto pr-2">
          <div className="bg-[#151A23] p-5 rounded-xl border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
              <FileText size={16} className="text-blue-400" /> Key Attributes
            </h3>
            <div className="space-y-4">
              {[
                { label: 'Amount', value: exception.amount },
                { label: 'Counterparty', value: exception.entity },
                { label: 'SLA Deadline', value: '45 mins remaining', alert: true },
                { label: 'Source System', value: 'Fusion / MQ' },
              ].map((item) => (
                <div key={item.label}>
                  <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">{item.label}</div>
                  <div className={`text-sm font-mono ${item.alert ? 'text-orange-400' : 'text-slate-200'}`}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-[#151A23] p-5 rounded-xl border border-slate-800">
            <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
              <Database size={16} className="text-purple-400" /> RAG Evidence
            </h3>
            <div className="space-y-3">
              <div className="p-3 bg-slate-900/50 rounded border border-slate-800 hover:border-blue-500/50 cursor-pointer transition-colors">
                <div className="text-xs text-blue-400 mb-1">Similar Case • 95% Match</div>
                <div className="text-sm text-slate-300">EX-2024-1120: Failed Settlement due to Holiday Cal...</div>
              </div>
              <div className="p-3 bg-slate-900/50 rounded border border-slate-800 hover:border-blue-500/50 cursor-pointer transition-colors">
                <div className="text-xs text-blue-400 mb-1">Policy Doc</div>
                <div className="text-sm text-slate-300">SOP-FIN-001: Handling Currency Mismatches v2.4</div>
              </div>
            </div>
          </div>
        </div>

        {/* Center: Agentic Chain of Thought */}
        <div className="col-span-6 flex flex-col gap-6 overflow-hidden">
          <div className="bg-[#151A23] border border-slate-800 rounded-xl flex-1 flex flex-col overflow-hidden">
             <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-[#1a1f2e]">
               <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                 <BrainCircuit size={16} className="text-pink-500" /> Agentic Reasoning Engine
               </h3>
               <span className="text-xs px-2 py-1 bg-slate-800 rounded text-slate-400 border border-slate-700">Model: Gemini 1.5 Pro</span>
             </div>
             <div className="p-6 overflow-y-auto space-y-6">
                {AGENT_THOUGHTS.map((thought, idx) => (
                  <div key={thought.step} className="flex gap-4 group">
                    <div className="flex flex-col items-center">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2 ${thought.status === 'complete' ? 'bg-emerald-900/30 border-emerald-500/50 text-emerald-400' : 'bg-blue-900/30 border-blue-500/50 text-blue-400 animate-pulse'}`}>
                        {thought.step}
                      </div>
                      {idx !== AGENT_THOUGHTS.length - 1 && <div className="w-0.5 flex-1 bg-slate-800 my-2 group-hover:bg-slate-700 transition-colors" />}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="flex justify-between items-start mb-1">
                        <span className="text-sm font-semibold text-slate-200">{thought.action}</span>
                        <span className="text-xs text-slate-500 font-mono">{thought.time}</span>
                      </div>
                      <p className="text-sm text-slate-400 leading-relaxed bg-[#0B0E14] p-3 rounded border border-slate-800/50">
                        {thought.detail}
                      </p>
                    </div>
                  </div>
                ))}
             </div>
             {/* Interaction Bar */}
             <div className="p-4 bg-[#1a1f2e] border-t border-slate-800 flex gap-2">
                <input type="text" placeholder="Intervene or ask agent to clarify..." className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"/>
                <button className="bg-slate-700 hover:bg-slate-600 text-white px-3 py-2 rounded transition-colors"><Send size={16} /></button>
             </div>
          </div>
        </div>

        {/* Right: Actions & Playbook */}
        <div className="col-span-3 space-y-6 overflow-y-auto">
           <div className="bg-[#151A23] p-5 rounded-xl border border-slate-800">
             <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
               <Workflow size={16} className="text-orange-400" /> Recommended Playbook
             </h3>
             <div className="space-y-2">
               <div className="flex items-center gap-3 p-2 rounded hover:bg-slate-800 transition-colors opacity-50">
                 <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-[10px] text-slate-500">1</div>
                 <span className="text-sm text-slate-400 line-through">Verify Nostro Balance</span>
               </div>
               <div className="flex items-center gap-3 p-2 rounded bg-blue-900/20 border border-blue-900/50">
                 <div className="w-5 h-5 rounded-full border-2 border-blue-500 flex items-center justify-center text-[10px] text-white bg-blue-600">2</div>
                 <span className="text-sm text-white font-medium">Contact Counterparty</span>
               </div>
               <div className="flex items-center gap-3 p-2 rounded hover:bg-slate-800 transition-colors">
                 <div className="w-5 h-5 rounded-full border border-slate-600 flex items-center justify-center text-[10px] text-slate-500">3</div>
                 <span className="text-sm text-slate-400">Force Settle</span>
               </div>
             </div>
             <button className="w-full mt-4 py-2 bg-slate-800 hover:bg-slate-700 text-blue-400 text-xs font-medium uppercase tracking-wider rounded border border-slate-700 transition-colors">
               View Full Workflow
             </button>
           </div>

           <div className="bg-[#151A23] p-5 rounded-xl border border-slate-800">
             <h3 className="text-sm font-semibold text-slate-300 mb-4 flex items-center gap-2">
               <Share2 size={16} className="text-slate-400" /> Collaborators
             </h3>
             <div className="flex -space-x-2 mb-4">
               <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs text-white ring-2 ring-[#151A23]">AI</div>
               <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-xs text-white ring-2 ring-[#151A23]">JD</div>
               <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs text-slate-300 ring-2 ring-[#151A23]">+2</div>
             </div>
             <div className="text-xs text-slate-500">
               Last active: <span className="text-slate-300">Jane Doe (Supervisor)</span> viewed 2m ago.
             </div>
           </div>
        </div>
      </div>
    </div>
  );
};

const WorkflowBuilder = () => {
  return (
    <div className="h-full bg-[#0B0E14] relative overflow-hidden flex">
      {/* Sidebar Palette */}
      <div className="w-64 bg-[#151A23] border-r border-slate-800 p-4 flex flex-col gap-6">
        <div>
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Logic Blocks</h3>
          <div className="space-y-2">
            {['Trigger: Exception Created', 'Condition: Severity > High', 'Action: LLM Analysis', 'Action: Email Stakeholder'].map((item) => (
              <div key={item} className="p-3 bg-slate-800 border border-slate-700 rounded text-sm text-slate-300 cursor-move hover:border-blue-500 transition-colors shadow-sm">
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Canvas Area (Mock) */}
      <div className="flex-1 relative bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')] bg-slate-900/50">
        <div className="absolute top-4 right-4 flex gap-2">
          <button className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-500 shadow-lg shadow-blue-900/20">Save & Deploy</button>
        </div>
        
        {/* Nodes Mockup */}
        <div className="absolute top-1/4 left-1/4 w-[600px] h-[400px]">
           <svg className="absolute inset-0 w-full h-full pointer-events-none z-0">
             <path d="M150,50 C250,50 250,150 350,150" stroke="#334155" strokeWidth="2" fill="none" />
             <path d="M350,150 C450,150 450,250 550,250" stroke="#334155" strokeWidth="2" fill="none" />
             <path d="M350,150 C450,150 450,50 550,50" stroke="#334155" strokeWidth="2" fill="none" />
           </svg>

           <div className="absolute top-0 left-0 p-4 bg-emerald-900/80 border border-emerald-700 rounded-lg shadow-xl w-48 backdrop-blur-sm">
             <div className="text-xs font-bold text-emerald-400 mb-1">TRIGGER</div>
             <div className="text-sm text-white">New Trade Failure</div>
           </div>

           <div className="absolute top-[120px] left-[300px] p-4 bg-blue-900/80 border border-blue-700 rounded-lg shadow-xl w-48 backdrop-blur-sm">
             <div className="text-xs font-bold text-blue-400 mb-1">AI AGENT</div>
             <div className="text-sm text-white">Classify & Route</div>
           </div>

           <div className="absolute top-[220px] left-[500px] p-4 bg-slate-800 border border-slate-600 rounded-lg shadow-xl w-48 backdrop-blur-sm">
             <div className="text-xs font-bold text-slate-400 mb-1">HUMAN LOOP</div>
             <div className="text-sm text-white">Approval Queue</div>
           </div>

           <div className="absolute top-[20px] left-[500px] p-4 bg-purple-900/80 border border-purple-700 rounded-lg shadow-xl w-48 backdrop-blur-sm">
             <div className="text-xs font-bold text-purple-400 mb-1">SYSTEM</div>
             <div className="text-sm text-white">Auto-Correct Ledger</div>
           </div>
        </div>
      </div>
    </div>
  );
};

const DashboardAnalytics = () => {
  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
       <div className="grid grid-cols-4 gap-6">
         {[
           { label: 'Pending Exceptions', val: '412', delta: '+12%', color: 'text-white' },
           { label: 'Avg Resolution Time', val: '4m 12s', delta: '-8%', color: 'text-emerald-400' },
           { label: 'Straight Through Rate', val: '89.4%', delta: '+2.1%', color: 'text-blue-400' },
           { label: 'Cost Saved (AI)', val: '$1.2M', delta: 'YTD', color: 'text-purple-400' },
         ].map((stat, i) => (
           <div key={i} className="bg-[#151A23] p-6 rounded-xl border border-slate-800 shadow-sm relative overflow-hidden group">
             <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
               <BarChart3 size={40} className="text-slate-400" />
             </div>
             <div className="text-slate-400 text-sm font-medium mb-2">{stat.label}</div>
             <div className={`text-3xl font-bold ${stat.color}`}>{stat.val}</div>
             <div className="text-xs text-slate-500 mt-2 font-mono flex items-center gap-1">
                <span className={stat.delta.includes('+') ? 'text-emerald-500' : 'text-slate-500'}>{stat.delta}</span> vs last week
             </div>
           </div>
         ))}
       </div>

       <div className="grid grid-cols-2 gap-6 h-[400px]">
          <div className="bg-[#151A23] p-6 rounded-xl border border-slate-800 flex flex-col">
            <h3 className="text-slate-200 font-semibold mb-6">Inflow vs Auto-Resolution</h3>
            <div className="flex-1 w-full min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={ANALYTICS_DATA}>
                  <defs>
                    <linearGradient id="colorVol" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorAuto" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                  <XAxis dataKey="time" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Area type="monotone" dataKey="volume" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorVol)" />
                  <Area type="monotone" dataKey="auto" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorAuto)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-[#151A23] p-6 rounded-xl border border-slate-800 flex flex-col">
            <h3 className="text-slate-200 font-semibold mb-6">Exceptions by Domain</h3>
            <div className="flex-1 w-full min-h-0">
               <ResponsiveContainer width="100%" height="100%">
                 <BarChart data={[
                   { name: 'Finance', val: 400 },
                   { name: 'Trading', val: 300 },
                   { name: 'Claims', val: 200 },
                   { name: 'Compliance', val: 150 },
                   { name: 'IT Ops', val: 100 },
                 ]} layout="vertical">
                   <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={true} vertical={false} />
                   <XAxis type="number" stroke="#64748b" hide />
                   <YAxis dataKey="name" type="category" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} width={80} />
                   <Tooltip cursor={{fill: '#1e293b'}} contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }} />
                   <Bar dataKey="val" fill="#6366f1" radius={[0, 4, 4, 0]} barSize={20} />
                 </BarChart>
               </ResponsiveContainer>
            </div>
          </div>
       </div>
    </div>
  );
};

export default function AgenticPlatform() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedException, setSelectedException] = useState(null);
  const [showCopilot, setShowCopilot] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // When a tab changes, clear detailed selection
  useEffect(() => {
    setSelectedException(null);
  }, [activeTab]);

  return (
    <div className="flex h-screen bg-[#0B0E14] text-slate-300 font-sans overflow-hidden selection:bg-blue-500/30">
      
      {/* Sidebar */}
      <aside 
        className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-[#151A23] border-r border-slate-800 flex flex-col transition-all duration-300 z-20`}
      >
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
           <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20">
             <Cpu size={20} />
           </div>
           {sidebarOpen && <span className="ml-3 font-bold text-lg text-white tracking-tight">Sentin<span className="text-blue-500">AI</span></span>}
        </div>

        <nav className="flex-1 py-6 px-3 space-y-1">
          {[
            { id: 'dashboard', icon: LayoutDashboard, label: 'Command Center' },
            { id: 'analytics', icon: BarChart3, label: 'Supervisor View' },
            { id: 'builder', icon: Network, label: 'Workflow Builder' },
            { id: 'config', icon: Settings, label: 'Domain Packs' },
          ].map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center px-3 py-3 rounded-lg transition-all duration-200 group ${
                  activeTab === item.id 
                    ? 'bg-blue-600/10 text-blue-400 border border-blue-600/20 shadow-sm' 
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                }`}
              >
                <Icon size={20} className={activeTab === item.id ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'} />
                {sidebarOpen && <span className="ml-3 text-sm font-medium">{item.label}</span>}
                {activeTab === item.id && sidebarOpen && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-400 shadow-lg shadow-blue-400/50" />}
              </button>
            )
          })}
        </nav>

        <div className="p-4 border-t border-slate-800">
           <button 
             onClick={() => setSidebarOpen(!sidebarOpen)}
             className="w-full flex items-center justify-center p-2 rounded hover:bg-slate-800 text-slate-500 transition-colors"
           >
             {sidebarOpen ? <ChevronRight size={20} className="rotate-180" /> : <ChevronRight size={20} />}
           </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/10 via-[#0B0E14] to-[#0B0E14]">
        
        {/* Top Header */}
        <header className="h-16 border-b border-slate-800 bg-[#0B0E14]/80 backdrop-blur-md flex items-center justify-between px-8 sticky top-0 z-10">
          <div className="flex items-center gap-6">
             {/* Tenant Selector */}
             <div className="flex items-center gap-2 text-slate-300 font-medium cursor-pointer hover:text-white transition-colors group">
               <span className="text-slate-500 group-hover:text-slate-400 transition-colors">Tenant:</span> 
               <span>Global FinCo</span>
               <ChevronDown size={14} className="text-slate-500 group-hover:text-slate-300 transition-colors" />
             </div>

             {/* Vertical Separator */}
             <div className="h-5 w-px bg-slate-800" />

             {/* Domain Selector */}
             <div className="flex items-center gap-2 text-slate-300 font-medium cursor-pointer hover:text-white transition-colors group">
               <span className="text-slate-500 group-hover:text-slate-400 transition-colors">Domain:</span> 
               <span>Capital Markets</span>
               <ChevronDown size={14} className="text-slate-500 group-hover:text-slate-300 transition-colors" />
             </div>
          </div>

          <div className="flex items-center gap-4">
             <div className="relative hidden md:block">
               <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
               <input 
                 type="text" 
                 placeholder="Search exceptions, entities..." 
                 className="bg-[#151A23] border border-slate-800 rounded-full pl-9 pr-4 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-blue-500 w-64 transition-all focus:w-80"
               />
             </div>
             <button className="relative p-2 text-slate-400 hover:text-white transition-colors">
               <Bell size={20} />
               <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-[#0B0E14]" />
             </button>
             
             {/* User Profile & Env Badge */}
             <div className="flex items-center gap-3 pl-4 border-l border-slate-800 ml-2">
                 <div className="flex flex-col items-end hidden md:flex">
                     <span className="text-sm font-medium text-slate-200">Austin Robertson</span>
                     <span className="text-[10px] text-emerald-400 font-mono bg-emerald-950/30 px-1.5 py-0.5 rounded border border-emerald-900/50 flex items-center gap-1">
                       <span className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse" />
                       ENV: PROD
                     </span>
                 </div>
                 <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 border border-slate-700 shadow-inner cursor-pointer hover:border-blue-400 transition-colors" />
             </div>
          </div>
        </header>

        {/* Dynamic View Area */}
        <div className="flex-1 overflow-auto p-8 relative">
          
          {selectedException ? (
            <ExceptionDetail 
              exception={selectedException} 
              onBack={() => setSelectedException(null)} 
            />
          ) : (
            <>
              {activeTab === 'dashboard' && (
                <div className="space-y-6 animate-in fade-in duration-500">
                  <div className="flex items-center justify-between">
                     <h2 className="text-2xl font-bold text-white tracking-tight">Operations Center</h2>
                     <div className="flex items-center gap-2 text-sm text-slate-400">
                       <Clock size={14} />
                       <span>Last updated: Live (WebSocket Connected)</span>
                     </div>
                  </div>

                  {/* Quick Stats Row */}
                  <div className="grid grid-cols-4 gap-4 mb-8">
                     <div className="bg-gradient-to-br from-red-900/20 to-transparent border-l-4 border-red-500 p-4 rounded-r-lg">
                       <div className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Critical Breaches</div>
                       <div className="text-2xl font-bold text-white">3</div>
                     </div>
                     <div className="bg-gradient-to-br from-blue-900/20 to-transparent border-l-4 border-blue-500 p-4 rounded-r-lg">
                        <div className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">AI Resolution Rate</div>
                        <div className="text-2xl font-bold text-white">94%</div>
                     </div>
                     <div className="bg-[#151A23] border border-slate-800 p-4 rounded-lg">
                        <div className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Pending Review</div>
                        <div className="text-2xl font-bold text-white">12</div>
                     </div>
                     <div className="bg-[#151A23] border border-slate-800 p-4 rounded-lg">
                        <div className="text-slate-400 text-xs uppercase font-bold tracking-wider mb-1">Total Volume (24h)</div>
                        <div className="text-2xl font-bold text-white">1,402</div>
                     </div>
                  </div>

                  <ExceptionsTable onSelectException={setSelectedException} />
                </div>
              )}

              {activeTab === 'analytics' && <DashboardAnalytics />}
              {activeTab === 'builder' && <WorkflowBuilder />}
              {activeTab === 'config' && (
                <div className="flex items-center justify-center h-full text-slate-500 flex-col gap-4">
                  <Settings size={48} className="opacity-20" />
                  <p>Domain Configuration & Policy Packs Loaded</p>
                </div>
              )}
            </>
          )}

          {/* Floating Copilot Trigger */}
          {!showCopilot && (
            <button 
              onClick={() => setShowCopilot(true)}
              className="fixed bottom-8 right-8 bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-full shadow-lg shadow-blue-600/30 transition-all hover:scale-110 z-40 group"
            >
              <Bot size={24} className="group-hover:rotate-12 transition-transform" />
            </button>
          )}

          {/* Copilot Window */}
          {showCopilot && <AICopilot onClose={() => setShowCopilot(false)} />}
          
        </div>
      </main>
    </div>
  );
}

// Icon helper for map
function Network(props) {
  return (
    <svg 
      {...props}
      xmlns="http://www.w3.org/2000/svg" 
      width="24" 
      height="24" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round"
    >
      <rect width="7" height="7" x="3" y="3" rx="1" />
      <rect width="7" height="7" x="14" y="3" rx="1" />
      <rect width="7" height="7" x="14" y="14" rx="1" />
      <rect width="7" height="7" x="3" y="14" rx="1" />
    </svg>
  );
}