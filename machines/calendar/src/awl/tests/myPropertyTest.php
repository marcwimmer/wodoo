<?php
/**
 * Created by JetBrains PhpStorm.
 * User: milan
 * Date: 7/8/13
 * Time: 12:03 PM
 * To change this template use File | Settings | File Templates.
 */

require_once 'inc/vComponent.php';

// compatibility with phpunit 6
if (!class_exists('\PHPUnit_Framework_TestCase') &&
    class_exists('\PHPUnit\Framework\TestCase')) {
    class_alias('\PHPUnit\Framework\TestCase', '\PHPUnit_Framework_TestCase');
}

class vPropertyTest extends PHPUnit_Framework_TestCase {

    function getData($filename){
        $file = fopen($filename, 'r');
        $data = fread($file, filesize($filename));
        fclose($file);
        return $data;
    }

    public function testProperty(){
        //$heapLines = new HeapLines($this->getData('tests/data/tzid_data.test'));
        $component = new vComponent($this->getData('tests/data/tzid_data.test'));
        $property = $component->getPropertyAt(0);

        $this->assertNotNull($property);
    }


    public function testPropertyGetName(){
        //$heapLines = new HeapLines($this->getData('tests/data/tzid_data.test'));
        $component = new vComponent($this->getData('tests/data/tzid_data.test'));
        $property = $component->getPropertyAt(0);

        $this->assertNotNull($property);

        $name = $property->Name();
        $this->assertStringStartsWith('PRODID', $name);


    }

    public function testPropertySetName(){
        //$heapLines = new HeapLines($this->getData('tests/data/tzid_data.test'));
        $component = new vComponent($this->getData('tests/data/tzid_data.test'));
        $property = $component->getPropertyAt(0);

        $property->Name('abcdef');
        $name = $property->Name();
        $this->assertStringStartsWith('ABCDEF', $name);
        $this->assertFalse($property->isValid());
    }


    public function testPropertyGetContent(){
        //$heapLines = new HeapLines($this->getData('tests/data/tzid_data.test'));
        $component = new vComponent($this->getData('tests/data/tzid_data.test'));
        $property = $component->getPropertyAt(0);

        $this->assertNotNull($property);

        $content = $property->Value();
        $this->assertStringStartsWith('-//davical.org//NONSGML', $content);


    }

    public function testPropertySetContnet(){
        //$heapLines = new HeapLines($this->getData('tests/data/tzid_data.test'));
        $component = new vComponent($this->getData('tests/data/tzid_data.test'));
        $property = $component->getPropertyAt(0);

        $property->Value('abcdef');
        $content = $property->Value();
        $this->assertStringStartsWith('abcdef', $content);
        $this->assertFalse($property->isValid());
    }


    public function testPropertyRenderFromString(){
        $property = new vProperty('PRODID:-//davical.org//NONSGML AWL Calendar//EN');

        $rendered = $property->Render();
        $this->assertStringStartsWith('PRODID:-//davical.org//NONSGML AWL Calendar//EN', $rendered);
    }

    public function testPropertyRenderFromParams(){
        $property = new vProperty();
        $property->Name('PRODID');
        $property->Value('-//davical.org//NONSGML AWL Calendar//EN');
        $rendered = $property->Render();
        $this->assertStringStartsWith('PRODID:-//davical.org//NONSGML AWL Calendar//EN', $rendered);
    }

    public function testPropertyRenderFromStringChangeName(){
        $property = new vProperty('PRODID:-//davical.org//NONSGML AWL Calendar//EN');

        $property->Name('VERSION');

        $rendered = $property->Render();
        $this->assertStringStartsWith('VERSION:', $rendered);
    }

    public function testSetParameterValue(){
        $property = new vProperty();
        $property->SetParameterValue("hello", "world");


        $value = $property->GetParameterValue("hello");
        $this->assertStringStartsWith("world", $value);
    }

    public function testSetParameterValueRender(){
        $property = new vProperty();
        $property->Name("universe");
        $property->SetParameterValue("hello", "world");


        $value = $property->Render();
        $this->assertStringStartsWith("UNIVERSE;HELLO=world:", $value);
    }

}
