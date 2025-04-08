import { Component, OnInit } from '@angular/core';
import { PhotoService } from 'src/app/modules/core/services/photo.service';

@Component({
  selector: 'app-photo-list',
  templateUrl: './photo-list.component.html',
  styleUrls: ['./photo-list.component.scss'],
})
export class PhotoListComponent implements OnInit {
  photos$ = this.photoService.photos;

  constructor(private photoService: PhotoService) {}

  ngOnInit() {
    this.photoService.getBlockchain().subscribe();
  }
}
