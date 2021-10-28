<?php
/**
 * Created by JetBrains PhpStorm.
 * User: milan
 * Date: 7/5/13
 * Time: 2:01 PM
 * To change this template use File | Settings | File Templates.
 */
require_once 'inc/vComponent.php';

// compatibility with phpunit 6
if (!class_exists('\PHPUnit_Framework_TestCase') &&
    class_exists('\PHPUnit\Framework\TestCase')) {
    class_alias('\PHPUnit\Framework\TestCase', '\PHPUnit_Framework_TestCase');
}

class vComponentTest extends PHPUnit_Framework_TestCase {
    public $testdata = <<<EOBODY1
BEGIN:VCALENDAR
PRODID:-//davical.org//NONSGML AWL Calendar//EN
VERSION:2.0
CALSCALE:GREGORIAN
EOBODY1;

    public $simpledata1 = <<<EOSIMPLEDATA1
BEGIN:VCALENDAR
SUMARY:12234567890122345678901223456789012234567890122345678901223467890
 122345678901223456789012
END:VCALENDAR
EOSIMPLEDATA1;

    function testParseComponents() {

       // $lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/tzid_data.test');
        $component = new vComponent($data);

        $this->assertEquals(8, $component->ComponentCount());
        $type = $component->GetType();
        $this->assertStringStartsWith('VCALENDAR', $type );
        $child = $component->getComponentAt(0);
        $this->assertNotNull($child);

        $childtype = $child->GetType();

        $this->assertStringStartsWith('VEVENT', $childtype );
        $this->assertEquals(1, $child->ComponentCount());
    }


    function testParseProperties(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);
        //$component = new vComponent();

        $this->assertEquals(4, $component->propertiesCount());
        $property1 = $component->getPropertyAt(0);
        $this->assertNotNull($property1);
    }


    function testGetNameProperties(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $this->assertEquals(4, $component->propertiesCount());
    }

    function te1stGetNameProperties2(){
        $lines = new HeapLines((new bigtestdata)->data);
        for($i = 0; $i < 100; $i++)
            $component = new vComponent($lines);

        //$this->assertEquals(4, $component->propertiesCount());
    }

    function testCollectParameterValues(){
//        /$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/tzid_data.test');
        $component = new vComponent($data);

        $parameters = $component->CollectParameterValues('TZID');

        $this->equalTo(4, count($parameters));
        $this->assertArrayHasKey('America/Los_Angeles', $parameters );
    }

    function testGetProperty(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $property = $component->GetProperty("VERSION");
        $this->assertNotNull($property);
        $this->assertInstanceOf('vProperty', $property);
    }

    function testGetPropertyAndChange(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);
        $this->assertTrue($component->isValid());
        $property = $component->GetProperty("VERSION");
        $this->assertTrue($component->isValid());
        $this->assertNotNull($property);
        $this->assertInstanceOf('vProperty', $property);
        $this->assertTrue($component->isValid());
        $property->Name("ahoj");
        $this->assertFalse($component->isValid());
    }


    function testGetNestedPropertyAndChange(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $nestedComponent = $component->getComponentAt(0);
        $nestedProperty = $nestedComponent->getPropertyAt(0);

        $name = $nestedProperty->Name();
        $this->assertTrue($component->isValid());
        $nestedProperty->Name($name . "TEST");
        $this->assertFalse($component->isValid());


    }

    function testGetPValue(){
//        /$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $property = $component->GetPValue("VERSION");
        $this->assertNotNull($property);
        $this->assertStringStartsWith('2.0', $property);
    }

    function testGetPropertiesWithName(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $properties = $component->GetProperties("VERSION");
        $this->assertNotNull($properties);
        $this->assertCount(1, $properties);
        $this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testGetPropertiesWithArray(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $properties = $component->GetProperties(["VERSION" => true, "CALSCALE" => true]);
        $this->assertNotNull($properties);
        $this->assertCount(2, $properties);
        $this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testGetPropertiesNoParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $properties = $component->GetProperties();
        $this->assertNotNull($properties);
        $this->assertCount(4, $properties);
        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }



    function testClearPropertiesNoParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $this->assertEquals(4, $component->propertiesCount());
        $component->ClearProperties();
        $this->assertEquals(0, $component->propertiesCount());
        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testClearPropertiesStringParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $this->assertEquals(4, $component->propertiesCount());
        $component->ClearProperties('VERSION');
        $this->assertEquals(3, $component->propertiesCount());
        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testClearPropertiesArrayParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $this->assertEquals(4, $component->propertiesCount());
        $component->ClearProperties(["VERSION" => true, "CALSCALE" => true]);
        $this->assertEquals(2, $component->propertiesCount());
        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }


    function testAddPropertyLikeProperty(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $property = new vProperty('HELLO');

        $this->assertEquals(4, $component->propertiesCount());
        $component->AddProperty($property);
        $this->assertEquals(5, $component->propertiesCount());
        $this->assertFalse($component->isValid());
        $p = $component->GetProperties(["HELLO" => true ]);
        $this->assertNotNull($p);

        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testAddPropertyLikeNameAndValue(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);


        $this->assertEquals(4, $component->propertiesCount());
        $component->AddProperty("HELLO", "WORLD");
        $this->assertEquals(5, $component->propertiesCount());
        $this->assertFalse($component->isValid());
        $p = $component->GetProperties(["HELLO" => true ]);
        $this->assertNotNull($p);

        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testComponentsNoParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/tzid_data.test');
        $component = new vComponent($data);


        $p = $component->GetComponents();
        $this->assertNotNull($p);
        $this->assertCount(8, $p);

        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testComponentsByName(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/tzid_data.test');
        $component = new vComponent($data);


        $p = $component->GetComponents("VEVENT");
        $this->assertNotNull($p);
        $this->assertCount(8, $p);
        foreach($p as $item){
            $this->assertStringStartsWith("VEVENT", $item->GetType());
        }

        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }

    function testComponentsByArray(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/tzid_data.test');
        $component = new vComponent($data);


        $p = $component->GetComponents(["VEVENT" => true]);
        $this->assertNotNull($p);
        $this->assertCount(8, $p);
        foreach($p as $item){
            $this->assertStringStartsWith("VEVENT", $item->GetType());
        }

        //$this->assertStringStartsWith('2.0', $properties[0]->Value());
    }


    function testClearComponentsNoParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);


        $component->ClearComponents();
        $this->assertEquals(0, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }

    function testClearComponentsArrayParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);


        $component->ClearComponents(["VEVENT" => true]);
        $this->assertEquals(0, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }

    function testClearComponentsStringParam(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);


        $component->ClearComponents("VEVENT");
        $this->assertEquals(0, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }

    function testSetComponent(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $newcomponent = new vComponent("BEGIN:VEVENT");
        $newcomponent2 = new vComponent("BEGIN:VEVENT");

        $component->SetComponents([$newcomponent, $newcomponent2]);
        $this->assertEquals(2, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }

    function testAddComponents(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $component = new vComponent($data);

        $newcomponent = new vComponent("BEGIN:VEVENT");
        $newcomponent2 = new vComponent("BEGIN:VEVENT");
        $newcomponent3 = new vComponent("BEGIN:VEVENT");


        $component->SetComponents([$newcomponent]);
        $component->AddComponent([$newcomponent2, $newcomponent3]);
        $this->assertEquals(3, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }

    function testAddComponentsWithEmptyComponents(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $component = new vComponent("VCALENDAR");

        $newcomponent = new vComponent("VEVENT");
        $newcomponent2 = new vComponent("VEVENT");
        $newcomponent3 = new vComponent("VEVENT");

        $this->assertEquals(0, $component->ComponentCount());
        $component->AddComponent([$newcomponent]);
        $this->assertEquals(1, $component->ComponentCount());

        $component->AddComponent([$newcomponent2, $newcomponent3]);
        $this->assertEquals(3, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }

    function testMaskComponents(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $component = new vComponent("VCALENDAR");

        $newcomponent = new vComponent("BEGIN:VEVENT");
        $newcomponent2 = new vComponent("BEGIN:MASK");
        $newcomponent3 = new vComponent("BEGIN:VEVENT");

        $component->AddComponent([$newcomponent, $newcomponent2, $newcomponent3]);
        $this->assertEquals(3, $component->ComponentCount());
        $component->MaskComponents(["MASK" => true]);
        $this->assertEquals(1, $component->ComponentCount());
        $this->assertFalse($component->isValid());

    }


    function testMaskProperties(){
        //$lines = new HeapLines((new bigtestdata)->testdata2);
        $component = new vComponent("BEGIN:VCALENDAR\nEND:VCALENDAR");

        $newcomponent = new vProperty("VEVENT");
        $newcomponent2 = new vProperty("MASK");
        $newcomponent3 = new vProperty("VEVENT");

        $component->AddProperty($newcomponent);
        $component->AddProperty($newcomponent2);
        $component->AddProperty($newcomponent3);
        $this->assertEquals(3, $component->propertiesCount());
        $component->MaskProperties(["MASK" => true]);
        $this->assertEquals(1, $component->propertiesCount());
        $this->assertFalse($component->isValid());

    }



    function te2stRenderCreated(){

        $component = new vComponent("BEGIN:VCALENDAR");
        $component->AddProperty("SUMARY", "12234567890122345678901223456789012234567890122345678901223467890122345678901223456789012");
        $text = $component->Render();

        //$this->assertStringStartsWith($this->simpledata1, $text);
    }

    function testRenderNoChanges2(){
//        $testdata = new bigtestdata();
//        //$lines = new HeapLines($this->simpledata1);
//        $component = new vComponent((new bigtestdata)->testdata2);
//        //$component->AddProperty("SUMARY", "12234567890122345678901223456789012234567890122345678901223467890122345678901223456789012");
//        $text = $component->Render();

        //$this->assertStringStartsWith($this->simpledata1, $text);
    }

    function getData($filename){
        $file = fopen($filename, 'r');
        $data = fread($file, filesize($filename));
        fclose($file);
        return $data;
    }

    function testInnerAlarmPresent(){
        $data = $this->getData('tests/data/inner_valarmdata.test');
        $vComponent = new vComponent($data);
        $this->assertEquals(4, $vComponent->propertiesCount());
        $components = $vComponent->GetComponents();

        $this->assertEquals(1, count($components));
        $inner = $components[0];
        $this->assertEquals(1, $inner->ComponentCount());
        $this->assertEquals(20, $inner->propertiesCount());
        $this->assertEquals(5, $inner->GetComponents()[0]->propertiesCount());
    }

}
