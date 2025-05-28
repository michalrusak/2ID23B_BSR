import { Component, OnInit, OnDestroy } from '@angular/core';
import {
  P2PService,
  Peer,
  TorrentFile,
} from 'src/app/modules/core/services/p2p.service';
import { Observable, Subject, interval, of } from 'rxjs';
import { takeUntil, switchMap, catchError } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-p2p-dashboard',
  templateUrl: './p2p-dashboard.component.html',
  styleUrls: ['./p2p-dashboard.component.scss'],
})
export class P2PDashboardComponent implements OnInit, OnDestroy {
  peers$: Observable<Peer[]>;
  torrents$: Observable<TorrentFile[]>;
  selectedNode: string | null = null;
  networkStatus: { [key: string]: boolean } = {
    node1: false,
    node2: false,
    node3: false,
    node4: false,
    node5: false,
    node6: false,
  };
  lastAction: string = 'No actions performed';
  testingFile: File | null = null;
  infohash: string = '';

  private destroy$ = new Subject<void>();

  constructor(private p2pService: P2PService, private http: HttpClient) {
    this.peers$ = this.p2pService.peers;
    this.torrents$ = this.p2pService.torrents;
  }

  ngOnInit(): void {
    this.refreshData();

    // Setup auto-refresh with error handling
    interval(30000)
      .pipe(
        takeUntil(this.destroy$),
        switchMap(() => {
          this.lastAction = 'Refreshing data...';
          return of(null).pipe(
            switchMap(() => this.refreshData()),
            catchError((error) => {
              console.error('Error in auto-refresh:', error);
              this.lastAction = 'Auto-refresh failed';
              return of(null);
            })
          );
        })
      )
      .subscribe();
  }

  refreshData(): Observable<any> {
    // Fetch peers with error handling
    this.p2pService
      .fetchPeers()
      .pipe(
        catchError((error) => {
          console.error('Error fetching peers:', error);
          return of([]);
        })
      )
      .subscribe();

    // Fetch torrents with error handling
    this.p2pService
      .fetchTorrents()
      .pipe(
        catchError((error) => {
          console.error('Error fetching torrents:', error);
          return of([]);
        })
      )
      .subscribe();

    // Check node health
    this.checkNodesHealth();

    // Return an observable that completes when all checks are done
    return of(null);
  }

  checkNodesHealth(): void {
    const nodes = [1, 2, 3, 4, 5, 6];
    nodes.forEach((nodeId) => {
      this.http
        .get<any>(`http://localhost:500${nodeId}/blockchain/health`, {})
        .pipe(
          takeUntil(this.destroy$),
          catchError((error) => {
            console.log(`Node ${nodeId} is not healthy:`, error.message);
            this.networkStatus[`node${nodeId}`] = false;
            return of({ status: 'unhealthy' });
          })
        )
        .subscribe((response) => {
          this.networkStatus[`node${nodeId}`] = response.status === 'healthy';
        });
    });
  }

  selectNode(nodeId: string): void {
    this.selectedNode = nodeId;
    this.lastAction = `Selected node: ${nodeId}`;
  }

  simulateNodeFailure(nodeId: number): void {
    this.p2pService
      .simulateFailure(nodeId, 'node_down')
      .pipe(takeUntil(this.destroy$))
      .subscribe(
        () => {
          this.lastAction = `Simulated failure for node${nodeId}`;
          this.networkStatus[`node${nodeId}`] = false;
          setTimeout(() => this.refreshData(), 1000);
        },
        (error) => {
          this.lastAction = `Error simulating failure: ${error.message}`;
        }
      );
  }

  simulateDataCorruption(nodeId: number): void {
    this.p2pService
      .simulateFailure(nodeId, 'data_corruption')
      .pipe(takeUntil(this.destroy$))
      .subscribe(
        () => {
          this.lastAction = `Simulated data corruption for node${nodeId}`;
          setTimeout(() => this.refreshData(), 1000);
        },
        (error) => {
          this.lastAction = `Error simulating corruption: ${error.message}`;
        }
      );
  }

  simulateNetworkPartition(): void {
    // Randomly disconnect some nodes from others
    const nodes = [1, 2, 3, 4, 5, 6];
    const partition1 = nodes.slice(0, 3);
    const partition2 = nodes.slice(3);

    partition1.forEach((node) => {
      partition2.forEach((targetNode) => {
        this.http
          .post<any>(
            `http://localhost:500${node}/blockchain/simulate/partition`,
            { targetNode: `node${targetNode}` }
          )
          .pipe(takeUntil(this.destroy$))
          .subscribe();
      });
    });

    this.lastAction = 'Simulated network partition between nodes 1-3 and 4-6';
    setTimeout(() => this.refreshData(), 1000);
  }

  onFileSelected(event: any): void {
    const file = event.target.files?.[0];
    if (file) {
      this.testingFile = file;
      this.lastAction = `Selected file: ${file.name}`;
    }
  }

  uploadFileTorrent(): void {
    if (!this.testingFile) {
      this.lastAction = 'No file selected';
      return;
    }

    const formData = new FormData();
    formData.append('file', this.testingFile);

    this.http
      .post<any>(
        'http://localhost:5001/blockchain/p2p/create-torrent',
        formData
      )
      .pipe(takeUntil(this.destroy$))
      .subscribe(
        (response) => {
          this.infohash = response.infohash;
          this.lastAction = `Created torrent with infohash: ${response.infohash}`;
          setTimeout(() => this.refreshData(), 1000);
        },
        (error) => {
          this.lastAction = `Error creating torrent: ${error.message}`;
        }
      );
  }

  downloadTorrent(): void {
    if (!this.infohash) {
      this.lastAction = 'No infohash provided';
      return;
    }

    this.http
      .get<any>(
        `http://localhost:5001/blockchain/p2p/download/${this.infohash}`
      )
      .pipe(takeUntil(this.destroy$))
      .subscribe(
        (response) => {
          this.lastAction = `Downloaded torrent: ${
            response.success ? 'Success' : 'Failed'
          }`;
          setTimeout(() => this.refreshData(), 1000);
        },
        (error) => {
          this.lastAction = `Error downloading torrent: ${error.message}`;
        }
      );
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
