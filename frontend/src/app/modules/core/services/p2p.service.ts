import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, interval, of } from 'rxjs';
import { map, switchMap, tap, catchError } from 'rxjs/operators';
import { environment } from 'src/environments/environment.development';

export interface Peer {
  node_id: string;
  address: string;
  isActive: boolean;
  latency?: number;
}

export interface TorrentFile {
  infohash: string;
  name: string;
  size: number;
  peers: string[];
  created: number;
}

@Injectable({
  providedIn: 'root',
})
export class P2PService {
  private readonly apiUrl = environment.apiURL;
  private peers$ = new BehaviorSubject<Peer[]>([]);
  private torrents$ = new BehaviorSubject<TorrentFile[]>([]);

  constructor(private http: HttpClient) {
    // Start periodic peer updates
    interval(10000)
      .pipe(
        switchMap(() =>
          this.fetchPeers().pipe(
            catchError((error) => {
              console.error('Error in peer update interval:', error);
              return of([]);
            })
          )
        )
      )
      .subscribe();
  }

  get peers(): Observable<Peer[]> {
    return this.peers$.asObservable();
  }

  get torrents(): Observable<TorrentFile[]> {
    return this.torrents$.asObservable();
  }

  fetchPeers(): Observable<Peer[]> {
    return this.http.get<any>(`${this.apiUrl}/blockchain/p2p/peers`).pipe(
      map((response) => {
        const peers = response?.peers || [];
        return peers.map((address: string) => {
          try {
            if (!address)
              return {
                node_id: 'unknown',
                address: 'unknown',
                isActive: false,
              };
            const parts = address.split('://')[1]?.split(':');
            const node_id = parts?.[0] || 'unknown';
            return {
              node_id,
              address,
              isActive: true,
            };
          } catch (e) {
            console.error('Error parsing peer address:', address, e);
            return {
              node_id: 'unknown',
              address: String(address),
              isActive: false,
            };
          }
        });
      }),
      tap((peers) => this.peers$.next(peers)),
      catchError((error) => {
        console.error('Error fetching peers:', error);
        return of([]);
      })
    );
  }

  fetchTorrents(): Observable<TorrentFile[]> {
    return this.http.get<any>(`${this.apiUrl}/blockchain/p2p/torrents`).pipe(
      map((response) => response?.torrents || []),
      tap((torrents) => this.torrents$.next(torrents)),
      catchError((error) => {
        console.error('Error fetching torrents:', error);
        return of([]);
      })
    );
  }

  createTorrent(data: any): Observable<any> {
    return this.http.post<any>(
      `${this.apiUrl}/blockchain/p2p/create-torrent`,
      data
    );
  }

  downloadTorrent(infohash: string): Observable<any> {
    return this.http.get<any>(
      `${this.apiUrl}/blockchain/p2p/download/${infohash}`
    );
  }

  getMagnetLink(infohash: string): Observable<string> {
    return this.http
      .get<any>(`${this.apiUrl}/blockchain/p2p/magnet/${infohash}`)
      .pipe(map((response) => response.magnet));
  }

  checkPeerHealth(peer: string): Observable<boolean> {
    return this.http.get<any>(`${peer}/health`).pipe(
      map((response) => response.status === 'healthy'),
      tap((isHealthy) => {
        const currentPeers = this.peers$.value;
        const updatedPeers = currentPeers.map((p) => {
          if (p.address === peer) {
            return { ...p, isActive: isHealthy };
          }
          return p;
        });
        this.peers$.next(updatedPeers);
      }),
      catchError((error) => {
        console.error(`Error checking health for peer ${peer}:`, error);
        // Mark peer as inactive due to error
        const currentPeers = this.peers$.value;
        const updatedPeers = currentPeers.map((p) => {
          if (p.address === peer) {
            return { ...p, isActive: false };
          }
          return p;
        });
        this.peers$.next(updatedPeers);
        return of(false);
      })
    );
  }

  simulateFailure(nodeId: number, failureType: string): Observable<any> {
    return this.http.post<any>(
      `http://localhost:500${nodeId}/blockchain/simulate/failure`,
      { type: failureType }
    );
  }
}
