import 'package:flutter_test/flutter_test.dart';
import 'package:pyrestus_app/main.dart';

void main() {
  testWidgets('Pyrestus home page renders', (WidgetTester tester) async {
    await tester.pumpWidget(const App());

    expect(find.text('Pyrestus'), findsOneWidget);
    expect(find.text('Ultrasound research tools'), findsOneWidget);
    expect(find.text('Start a new conversion'), findsOneWidget);
  });
}
