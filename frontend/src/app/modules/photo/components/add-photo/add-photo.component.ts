import { Component, OnDestroy } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';
import { PhotoService } from 'src/app/modules/core/services/photo.service';
import { PhotoStateService } from 'src/app/modules/core/services/photo.state';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-add-photo',
  templateUrl: './add-photo.component.html',
  styleUrls: ['./add-photo.component.scss'],
})
export class AddPhotoComponent implements OnDestroy {
  private destroy$ = new Subject<void>();
  state$ = this.photoState.getState();
  chain: any[] = [];

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
  }

  fetchChain() {
    this.http
      .get<any>('http://localhost:5001/blockchain/chain')
      .pipe(takeUntil(this.destroy$))
      .subscribe((data) => {
        this.chain = data.chain;
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
