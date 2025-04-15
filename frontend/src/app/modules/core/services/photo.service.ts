import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject, tap } from 'rxjs';
import { environment } from 'src/environments/environment';

@Injectable({
  providedIn: 'root',
})
export class PhotoService {
  private apiUrl = environment.apiURL;

  // Keep track of node status
  private nodeStatus = new BehaviorSubject<{ [key: number]: boolean }>({
    1: true,
    2: true,
    3: true,
    4: true,
    5: true,
    6: true,
  });

  nodeStatus$ = this.nodeStatus.asObservable();

  constructor(private http: HttpClient) {
    // Initialize by checking node status
    this.checkAllNodesStatus();
  }

  uploadAndProcessPhoto(file: File): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post(
      `${this.apiUrl}/blockchain/transactions/new/image`,
      formData
    );
  }

  getChain(nodeId: number = 1): Observable<any> {
    return this.http.get(`http://localhost:500${nodeId}/blockchain/chain`);
  }

  getNodes(): Observable<any> {
    return this.http.get(`${this.apiUrl}/nodes`);
  }

  toggleNode(nodeId: number, active: boolean): Observable<any> {
    if (!active) {
      return this.http
        .post(`http://localhost:500${nodeId}/blockchain/simulate/failure`, {
          type: 'node_down',
        })
        .pipe(
          tap(() => {
            const currentStatus = this.nodeStatus.value;
            this.nodeStatus.next({
              ...currentStatus,
              [nodeId]: false,
            });
          })
        );
    } else {
      // This would require an endpoint to bring a node back up
      // Since this is a simulation, you might need to add this functionality
      return this.http
        .post(`http://localhost:500${nodeId}/blockchain/simulate/recover`, {})
        .pipe(
          tap(() => {
            const currentStatus = this.nodeStatus.value;
            this.nodeStatus.next({
              ...currentStatus,
              [nodeId]: true,
            });
          })
        );
    }
  }

  simulateHashCorruption(nodeId: number): Observable<any> {
    return this.http.post(
      `http://localhost:500${nodeId}/blockchain/simulate/failure`,
      {
        type: 'hash_corruption',
      }
    );
  }

  simulateDataCorruption(nodeId: number): Observable<any> {
    return this.http.post(
      `http://localhost:500${nodeId}/blockchain/simulate/failure`,
      {
        type: 'data_corruption',
      }
    );
  }

  private checkAllNodesStatus() {
    // Check status of all nodes
    for (let i = 1; i <= 6; i++) {
      this.http
        .get(`http://localhost:500${i}/blockchain/status`, {
          observe: 'response',
        })
        .subscribe({
          next: () => {
            const currentStatus = this.nodeStatus.value;
            this.nodeStatus.next({
              ...currentStatus,
              [i]: true,
            });
          },
          error: () => {
            const currentStatus = this.nodeStatus.value;
            this.nodeStatus.next({
              ...currentStatus,
              [i]: false,
            });
          },
        });
    }
  }
}
