export interface User {
  id: number;
  username: string;
}

export interface LoginData {
  username: string;
  password: string;
}

export interface RegisterData extends LoginData {
  confirmPassword?: string;
}

export interface ResponseUser {
  id: number;
  username: string;
  token: string;
}

export interface MessageResponse {
  message: string;
}

export interface ImageResponse {
  message: string;
  image_id?: number;
}

export interface BlockchainResponse {
  message: string;
  chain?: any[];
  length?: number;
}

export interface TorrentInfo {
  info_hash: string;
  name: string;
  size: number;
  created_by: string;
  comment: string;
  announce_urls: string[];
}
