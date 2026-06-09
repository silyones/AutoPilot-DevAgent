'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import {
  PIPELINE_NODES,
  NODE_ORDER,
  mapAgentToNode,
  initialNodeStates,
  PANEL_CLASS,
} from '../lib/pipeline';
import { resolveApiBase, buildWsUrl, validatePrUrl } from '../lib/api';
import ErrorBoundary from '../components/ErrorBoundary';
import ControlPanel from '../components/ControlPanel';
import PipelineDiagram from '../components/PipelineDiagram';
import RecentActivity from '../components/RecentActivity';
import ReportPanel from '../components/ReportPanel';

function HomePage() {
  const [prUrl, setPrUrl] = useState('');
  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState('IDLE');
  const [duration, setDuration] = useState('');
  const [error, setError] = useState('');
  const [nodeStates, setNodeStates] = useState(initialNodeStates);
  const [recentLog, setRecentLog] = useState([]);
  const [report, setReport] = useState(null);
  const [retryActive, setRetryActive] = useState(false);

  const wsRef = useRef(null);
  const timerRef = useRef(null);
  const startTsRef = useRef(null);
  const currentNodeRef = useRef(null);

  const addLog = useCallback((agent, message) => {
    setRecentLog((prev) => {
      const entry = { agent: agent || 'System', message, ts: new Date().toLocaleTimeString() };
      return [...prev.slice(-4), entry];
    });
  }, []);

  const setNode = useCallback((nodeId, state) => {
    if (!nodeId) return;
    setNodeStates((prev) => ({ ...prev, [nodeId]: state }));
  }, []);

  const markPreviousDone = useCallback((activeNodeId) => {
    const idx = NODE_ORDER.indexOf(activeNodeId);
    if (idx <= 0) return;
    setNodeStates((prev) => {
      const next = { ...prev };
      for (let i = 0; i < idx; i++) {
        const id = NODE_ORDER[i];
        if (next[id] === 'RUNNING' || next[id] === 'DONE') next[id] = 'DONE';
      }
      return next;
    });
  }, []);

  const handleAgentProgress = useCallback(
    (agent, message, action) => {
      const nodeId = mapAgentToNode(agent);
      if (!nodeId) return;

      if (action?.includes('fix_bugs_attempt') && (action.includes('2') || action.includes('3'))) {
        setRetryActive(true);
        setNode('fixer', 'RUNNING');
        setNode('tester', 'WAITING');
      }

      if (action?.includes('run_tests') && message?.toLowerCase().includes('fail')) {
        setRetryActive(true);
        setNode('tester', 'FAILED');
        setTimeout(() => setNode('fixer', 'RUNNING'), 400);
      }

      markPreviousDone(nodeId);
      setNode(nodeId, 'RUNNING');
      currentNodeRef.current = nodeId;
      addLog(agent, message);
    },
    [setNode, markPreviousDone, addLog],
  );

  const reset = useCallback(() => {
    setNodeStates(initialNodeStates());
    setRecentLog([]);
    setReport(null);
    setError('');
    setRetryActive(false);
    setDuration('');
    currentNodeRef.current = null;
    try {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    } catch (e) {
      console.warn('WebSocket close failed:', e);
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startTimer = () => {
    startTsRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setDuration(((Date.now() - startTsRef.current) / 1000).toFixed(1) + 's');
    }, 100);
  };

  const stopTimer = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const startReview = async () => {
    const validation = validatePrUrl(prUrl);
    if (!validation.ok) {
      setError(validation.error);
      return;
    }

    reset();
    setRunning(true);
    setStatus('IN PROGRESS');
    startTimer();

    let sessionId;
    try {
      const resp = await fetch(`${resolveApiBase()}/api/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pr_url: validation.url }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      if (!data.success) throw new Error(data.error || 'Server error');
      sessionId = data.session_id;
    } catch (e) {
      setError('Failed to start: ' + (e?.message || 'Unknown error'));
      setStatus('ERROR');
      setRunning(false);
      stopTimer();
      return;
    }

    addLog('AutoPilot', 'Pipeline started — session ' + sessionId.slice(0, 8) + '…');
    setNode('fetcher', 'RUNNING');
    currentNodeRef.current = 'fetcher';

    let ws;
    try {
      ws = new WebSocket(buildWsUrl(sessionId));
    } catch (e) {
      setError('WebSocket failed: ' + (e?.message || 'Unknown error'));
      setStatus('ERROR');
      setRunning(false);
      stopTimer();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => addLog('WebSocket', 'Connected — waiting for updates…');

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch (e) {
        console.warn('Invalid WebSocket message:', e);
        return;
      }

      if (msg.type === 'start') {
        setNode('fetcher', 'RUNNING');
        addLog('System', msg.message || 'Pipeline running…');
      } else if (msg.type === 'progress') {
        handleAgentProgress(msg.agent, msg.message || msg.action, msg.action);
      } else if (msg.type === 'complete') {
        stopTimer();
        const r = msg.report || {};
        setReport(r);
        const st = r.status || 'PASSED';
        setStatus(st);
        setDuration((r.total_duration_seconds || 0).toFixed(2) + 's');
        const finalStates = {};
        PIPELINE_NODES.forEach((n) => {
          finalStates[n.id] = 'DONE';
        });
        setNodeStates(finalStates);
        setRetryActive(false);
        addLog('AutoPilot', 'Pipeline complete — ' + st);
        setRunning(false);
        try {
          ws.close();
        } catch (e) {
          console.warn(e);
        }
      } else if (msg.type === 'error') {
        stopTimer();
        setStatus('ERROR');
        setError(msg.message || 'Pipeline error');
        if (currentNodeRef.current) setNode(currentNodeRef.current, 'FAILED');
        addLog('Error', msg.message);
        setRunning(false);
        try {
          ws.close();
        } catch (e) {
          console.warn(e);
        }
      }
    };

    ws.onerror = () => addLog('WebSocket', 'Connection error');
  };

  useEffect(
    () => () => {
      try {
        if (wsRef.current) wsRef.current.close();
      } catch (e) {
        console.warn(e);
      }
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  return (
    <div className="max-w-[90rem] mx-auto px-6 sm:px-10 py-10">
      <div className="flex flex-col lg:flex-row gap-8">
        <div className="lg:w-[36%] xl:w-[34%] shrink-0">
          <ControlPanel
            prUrl={prUrl}
            setPrUrl={setPrUrl}
            running={running}
            startReview={startReview}
            error={error}
            status={status}
            duration={duration}
          />
        </div>
        <div className="lg:flex-1 min-w-0">
          <div className={`${PANEL_CLASS} h-full`}>
            <h2 className="text-xs uppercase text-pink tracking-wide mb-4">Live Pipeline</h2>
            <PipelineDiagram nodeStates={nodeStates} retryActive={retryActive} />
            <RecentActivity recentLog={recentLog} />
          </div>
        </div>
      </div>
      {report && <ReportPanel report={report} />}
    </div>
  );
}

export default function Page() {
  return (
    <ErrorBoundary>
      <HomePage />
    </ErrorBoundary>
  );
}
