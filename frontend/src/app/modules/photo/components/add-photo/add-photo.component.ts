import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject, takeUntil, interval } from 'rxjs';
import { PhotoService } from 'src/app/modules/core/services/photo.service';
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

  ngOnInit() {
    this.fetchChain();
    
    // Set up periodic refresh of chain
    interval(10000) // Refresh every 10 seconds
      .pipe(takeUntil(this.destroy$))
      .subscribe(() => this.fetchChain());
      
    // Subscribe to node status changes
    this.photoService.nodeStatus$
      .pipe(takeUntil(this.destroy$))
      .subscribe(nodeStatus => {
        this.nodes = this.nodes.map(node => ({
          ...node,
          active: nodeStatus[node.id] || false
        }));
      });
  }

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

  fetchChain() {
    // Try to get chain from the first active node
    const activeNode = this.nodes.find(node => node.active)?.id || 1;
    
    this.photoService.getChain(activeNode)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (data) => {
          this.chain = data.chain;
        },
        error: (err) => {
          console.error('Failed to fetch chain:', err);
        }
      });
  }

  toggleNode(nodeId: number) {
    const node = this.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    this.photoService.toggleNode(nodeId, !node.active)
      .subscribe({
        next: () => {
          // Status update is handled by the service
          this.fetchChain();
        },
        error: (err) => {
          console.error(`Failed to toggle node ${nodeId}:`, err);
        }
      });
  }

  simulateHashCorruption(nodeId: number) {
    this.photoService.simulateHashCorruption(nodeId)
      .subscribe({
        next: () => {
          console.log(`Hash corruption simulated on node ${nodeId}`);
          // Wait a bit then fetch the chain to see the effect
          setTimeout(() => this.fetchChain(), 2000);
        },
        error: (err) => {
          console.error(`Failed to simulate hash corruption on node ${nodeId}:`, err);
        }
      });
  }

  simulateDataCorruption(nodeId: number) {
    this.photoService.simulateDataCorruption(nodeId)
      .subscribe({
        next: () => {
          console.log(`Data corruption simulated on node ${nodeId}`);
          // Wait a bit then fetch the chain to see the effect
          setTimeout(() => this.fetchChain(), 2000);
        },
        error: (err) => {
          console.error(`Failed to simulate data corruption on node ${nodeId}:`, err);
        }
      });
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }
}