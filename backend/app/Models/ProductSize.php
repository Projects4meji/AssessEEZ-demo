<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\SoftDeletes;

class ProductSize extends Model
{
    use HasFactory;

    protected $fillable = [
        'id',
        'product_id',
        'size_id',
        'created_at',
        'updated_at',
        'deleted_at'
    ];
}
