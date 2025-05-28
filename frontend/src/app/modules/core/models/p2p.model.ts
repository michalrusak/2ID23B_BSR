export interface NetworkNode {
  id: string;
  name: string;
  status: 'active' | 'inactive' | 'failed';
  address: string;
  connections: string[];
}

export interface P2PStatistics {
  totalNodes: number;
  activeNodes: number;
  totalConnections: number;
  dataTransferred: number;
  errorsDetected: number;
}

export interface TorrentMetadata {
  infohash: string;
  name: string;
  pieceLength: number;
  pieces: number;
  totalLength: number;
  createdBy: string;
  creationDate: number;
}

export interface NetworkLink {
  source: string;
  target: string;
  strength: number;
}
