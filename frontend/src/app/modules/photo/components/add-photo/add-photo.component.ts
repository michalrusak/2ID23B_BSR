import { Component, OnDestroy, OnInit } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';
import {
  PhotoService,
  TorrentInfo,
} from 'src/app/modules/core/services/photo.service';
import { PhotoStateService } from 'src/app/modules/core/services/photo.state';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-add-photo',
  templateUrl: './add-photo.component.html',
  styleUrls: ['./add-photo.component.scss'],
})
export class AddPhotoComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();
  state$ = this.photoState.getState();
  chain: any[] = [];
  torrentInfo: TorrentInfo | null = null;
  isLoadingTorrentInfo = false;
  torrentDownloadError: string | null = null;

  nodes = [
    { id: 1, name: 'Node 1', active: true },
    { id: 2, name: 'Node 2', active: true },
    { id: 3, name: 'Node 3', active: true },
    { id: 4, name: 'Node 4', active: true },
    { id: 5, name: 'Node 5', active: true },
    { id: 6, name: 'Node 6', active: true },
  ];

  constructor(
    private photoService: PhotoService,
    private photoState: PhotoStateService,
    private http: HttpClient
  ) {}

  onFileSelected(event: any) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!this.validateFile(file)) {
      this.photoState.setError(
        'Please select a valid image file (jpg, png, gif) under 5MB'
      );
      return;
    }

    this.photoState.reset();
    this.photoState.setUploading(true);

    this.photoService.uploadAndProcessPhoto(file).subscribe({
      next: () => {
        this.photoState.setProgress(100);
        this.photoState.setSuccess(
          'Photo successfully uploaded and processed on blockchain'
        );
        this.fetchChain();
      },
      error: (error) => {
        this.photoState.setError(error.message || 'Failed to process photo');
      },
      complete: () => {
        this.photoState.setUploading(false);
      },
    });
  }

  private validateFile(file: File): boolean {
    const validTypes = ['image/jpeg', 'image/png', 'image/gif'];
    const maxSize = 5 * 1024 * 1024; // 5MB
    return validTypes.includes(file.type) && file.size <= maxSize;
  }

  ngOnInit() {
    this.fetchChain();
    this.fetchTorrentInfo();
  }

  fetchChain() {
    this.http
      .get<any>('http://localhost:5001/blockchain/chain')
      .pipe(takeUntil(this.destroy$))
      .subscribe((data) => {
        this.chain = data.chain;
      });
  }

  fetchTorrentInfo() {
    this.isLoadingTorrentInfo = true;
    this.torrentDownloadError = null;

    this.photoService
      .getTorrentInfo()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (response) => {
          this.torrentInfo = response.torrent_info;
          this.isLoadingTorrentInfo = false;
        },
        error: (error) => {
          console.error('Error fetching torrent info:', error);
          this.torrentDownloadError = 'Failed to fetch torrent information';
          this.isLoadingTorrentInfo = false;
        },
      });
  }

  downloadTorrentFile() {
    this.torrentDownloadError = null;

    this.photoService
      .getBlockchainTorrent()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (blob) => {
          const timestamp = new Date().getTime();
          this.photoService.downloadFile(
            blob,
            `blockchain_${timestamp}.torrent`
          );
        },
        error: (error) => {
          console.error('Error downloading torrent:', error);
          this.torrentDownloadError = 'Failed to download torrent file';
        },
      });
  }

  downloadBlockchainData() {
    this.torrentDownloadError = null;

    this.photoService
      .getBlockchainDataFile()
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (blob) => {
          const timestamp = new Date().getTime();
          this.photoService.downloadFile(
            blob,
            `blockchain_data_${timestamp}.json`
          );
        },
        error: (error) => {
          console.error('Error downloading blockchain data:', error);
          this.torrentDownloadError = 'Failed to download blockchain data file';
        },
      });
  }

  toggleNode(nodeId: number) {
    this.http
      .post(`http://localhost:500${nodeId}/blockchain/simulate/failure`, {
        type: 'node_down',
      })
      .subscribe(() => {
        const node = this.nodes.find((n) => n.id === nodeId);
        if (node) node.active = false;
      });
  }

  simulateHashCorruption(nodeId: number) {
    this.http
      .post(`http://localhost:500${nodeId}/blockchain/simulate/failure`, {
        type: 'hash_corruption',
      })
      .subscribe();
  }

  simulateDataCorruption(nodeId: number) {
    this.http
      .post(`http://localhost:500${nodeId}/blockchain/simulate/failure`, {
        type: 'data_corruption',
      })
      .subscribe();
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
