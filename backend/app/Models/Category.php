<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class Category extends Model
{
    use HasFactory, SoftDeletes;

    protected $fillable = [
        'id',
        'name',
        'parent_id',
        'created_at',
        'updated_at',
        'deleted_at'
    ];

    public function subcategories()
    {
        return $this->hasMany(SubCategory::class, 'category_id');
    }

    public function children()
    {
        return $this->hasMany(Category::class, 'parent_id')->with('children');
    }

    public function deleteWithChildren()
    {
        foreach ($this->children as $child) {
            $child->deleteWithChildren();
        }

        $this->delete();
    }

     public function parent()
    {
        return $this->belongsTo(Category::class, 'parent_id');
    }
}
