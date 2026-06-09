import axios from 'axios';
import type { QueryResponse, DatabaseStatus } from '@/types';

const API_BASE_URL = 'http://localhost:8001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 150000,
});

export const queryAgent = async (question: string, user_id?: string, session_id?: string): Promise<QueryResponse> => {
  const response = await api.post('/query', {
    question,
    user_id,
    session_id,
  });
  return response.data;
};

export const connectDatabase = async (db_type: string): Promise<{ status: string; message: string }> => {
  const response = await api.post('/connect', null, { params: { db_type } });
  return response.data;
};

export const disconnectDatabase = async (): Promise<{ status: string; message: string }> => {
  const response = await api.post('/disconnect');
  return response.data;
};

export const getDatabaseStatus = async (): Promise<DatabaseStatus> => {
  const response = await api.get('/database/status');
  return response.data;
};

export const getTools = async (): Promise<{ tools: string }> => {
  const response = await api.get('/tools');
  return response.data;
};

export const healthCheck = async (): Promise<{ status: string }> => {
  const response = await api.get('/health');
  return response.data;
};