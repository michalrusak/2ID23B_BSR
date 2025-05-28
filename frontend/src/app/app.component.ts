import { Component, OnInit } from '@angular/core';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit {
  title = 'Photo App';

  ngOnInit(): void {
    // Initialize the app
    console.log('App initialized');
  }
}
