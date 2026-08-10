import 'package:flutter/material.dart';
import 'features/home/home.dart';
void main()=>runApp(const App());
class App extends StatelessWidget{const App({super.key});@override Widget build(BuildContext c)=>MaterialApp(debugShowCheckedModeBanner:false,title:'Pyrestus',theme:ThemeData(useMaterial3:true,colorScheme:ColorScheme.fromSeed(seedColor:const Color(0xff2563eb)),scaffoldBackgroundColor:const Color(0xfff8fafc)),home:const Home());}
