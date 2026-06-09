import { useState, useEffect } from 'react';
import { Database, Wifi, WifiOff, RefreshCw } from 'lucide-react';
import { getDatabaseStatus, connectDatabase, disconnectDatabase } from '@/services/api';
import type { DatabaseStatus as DatabaseStatusType } from '@/types';

export default function DatabaseStatus() {
  const [status, setStatus] = useState<DatabaseStatusType | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const result = await getDatabaseStatus();
      setStatus(result);
    } catch (err) {
      setMessage('无法连接到后端服务');
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const result = await connectDatabase('mssql');
      setMessage(result.message);
      await fetchStatus();
    } catch (err) {
      setMessage('连接失败');
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      const result = await disconnectDatabase();
      setMessage(result.message);
      await fetchStatus();
    } catch (err) {
      setMessage('断开失败');
    }
  };

  if (!status) {
    return (
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-center gap-2">
        <RefreshCw className="w-4 h-4 text-gray-400 animate-spin" />
        <span className="text-sm text-gray-500">加载中...</span>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${status.connected ? 'bg-green-100' : 'bg-red-100'}`}>
            {status.connected ? (
              <Wifi className="w-5 h-5 text-green-600" />
            ) : (
              <WifiOff className="w-5 h-5 text-red-600" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-gray-500" />
              <span className="font-medium text-gray-700">数据库连接</span>
            </div>
            <span className={`text-sm ${status.connected ? 'text-green-600' : 'text-red-600'}`}>
              {status.connected
                ? `已连接: ${status.db_type}`
                : '未连接'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {!status.connected ? (
            <button
              onClick={handleConnect}
              disabled={isConnecting}
              className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 text-sm flex items-center gap-2"
            >
              {isConnecting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>连接中...</span>
                </>
              ) : (
                <>
                  <Wifi className="w-4 h-4" />
                  <span>连接</span>
                </>
              )}
            </button>
          ) : (
            <button
              onClick={handleDisconnect}
              className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 text-sm flex items-center gap-2"
            >
              <WifiOff className="w-4 h-4" />
              <span>断开</span>
            </button>
          )}
        </div>
      </div>
      {message && (
        <div className={`mt-2 text-sm ${message.includes('成功') ? 'text-green-600' : 'text-red-600'}`}>
          {message}
        </div>
      )}
    </div>
  );
}