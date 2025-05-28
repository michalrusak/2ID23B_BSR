import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule, Routes } from '@angular/router';
import { HttpClientModule } from '@angular/common/http';
import { P2PDashboardComponent } from './components/p2p-dashboard/p2p-dashboard.component';

const routes: Routes = [{ path: '', component: P2PDashboardComponent }];

@NgModule({
  declarations: [P2PDashboardComponent],
  imports: [
    CommonModule,
    FormsModule,
    HttpClientModule,
    RouterModule.forChild(routes),
  ],
  exports: [P2PDashboardComponent],
})
export class P2PModule {}
